"""
Views for the scheduling app.

This module contains class-based views for handling calendar and scheduling
HTTP requests. Views are organized by functionality:
- Calendar views for displaying shifts and time-off in weekly/monthly formats
- HTMX partial views for dynamic page updates
- Shift CRUD views for managing shifts
"""

from datetime import date, datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views import View
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView


class LandingView(View):
    """
    Public landing page for ShiftSync.

    Redirects authenticated users to the calendar.
    Shows marketing page to unauthenticated users.
    """

    def get(self, request):
        """
        Handle GET requests for the landing page.

        Returns:
            Redirect to calendar if user is authenticated,
            otherwise renders the landing page template.
        """
        if request.user.is_authenticated:
            return redirect('scheduling:calendar')
        return render(request, 'landing.html')

from .forms import DayOffRequestForm, PasswordChangeForm, ShiftForm, UserProfileForm
from .mixins import ManagerRequiredMixin
from .models import DayOffRequest, Department, Notification, Shift, TimeEntry, User
from .services import CalendarService, EmailService, HoursService, NotificationService


class CalendarView(LoginRequiredMixin, TemplateView):
    """
    Main calendar view displaying a weekly schedule.

    Shows shifts and approved day-off requests for the selected week.
    Managers see all shifts; employees see only published shifts plus
    their own unpublished shifts.

    URL Parameters:
        view_date (str, optional): Date in YYYY-MM-DD format to center the view.
            Defaults to today's date if not provided or invalid.

    Context Variables:
        view_date: The date used to determine the displayed week.
        week_start: Monday of the displayed week.
        week_end: Sunday of the displayed week.
        week_dates: List of 7 date objects (Mon-Sun).
        shifts_by_date: Dict mapping dates to lists of Shift objects.
        day_offs_by_date: Dict mapping dates to lists of DayOffRequest objects.
        prev_week: ISO date string for navigating to the previous week.
        next_week: ISO date string for navigating to the next week.
        today: Today's date for highlighting the current day.
    """

    template_name = 'scheduling/calendar.html'

    def get_context_data(self, **kwargs):
        """
        Build the context dictionary for the calendar template.

        Parses the view_date from URL kwargs, calculates week boundaries,
        and retrieves relevant shifts and day-off requests.
        """
        context = super().get_context_data(**kwargs)

        # Parse view_date from URL or use today as default
        view_date = self._parse_view_date()

        # Calculate week boundaries
        week_start, week_end = CalendarService.get_week_range(view_date)
        week_dates = CalendarService.get_week_dates(view_date)

        # Determine shift visibility based on user role
        user = self.request.user
        published_only = not user.is_manager

        # Retrieve shifts and day-offs for the week
        shifts_by_date = CalendarService.get_shifts_for_range(
            week_start, week_end, user=user, published_only=published_only
        )
        day_offs_by_date = CalendarService.get_day_offs_for_range(
            week_start, week_end, user=user
        )

        # Calculate navigation dates
        prev_week = (week_start - timedelta(days=7)).isoformat()
        next_week = (week_start + timedelta(days=7)).isoformat()

        context.update({
            'view_date': view_date,
            'week_start': week_start,
            'week_end': week_end,
            'week_dates': week_dates,
            'shifts_by_date': shifts_by_date,
            'day_offs_by_date': day_offs_by_date,
            'prev_week': prev_week,
            'next_week': next_week,
            'prev_period': prev_week,
            'next_period': next_week,
            'today': date.today(),
            'view_mode': 'week',
            'employees': User.objects.all(),
            'departments': Department.objects.all(),
        })
        return context

    def _parse_view_date(self) -> date:
        """
        Parse the view_date from URL kwargs.

        Returns:
            The parsed date, or today's date if parsing fails or no date provided.
        """
        view_date_str = self.kwargs.get('view_date')
        if view_date_str:
            try:
                return datetime.strptime(view_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        return date.today()


class CalendarGridPartial(LoginRequiredMixin, TemplateView):
    """
    HTMX partial view for calendar navigation.

    Returns only the calendar grid HTML fragment for use with HTMX
    navigation (prev/next buttons). Supports both week and month views
    with animation direction for smooth transitions.

    Query Parameters:
        date (str): Date in YYYY-MM-DD format for the target period.
        direction (str): Animation direction ('prev' or 'next').
            Defaults to 'next'.
        view_mode (str): Calendar view mode ('week' or 'month').
            Defaults to 'week'.

    Context Variables:
        For week mode: Same as CalendarView.
        For month mode: month_weeks, current_month, current_year, day_names.
        Both modes include: direction, view_mode, prev_period, next_period.
    """

    def get_template_names(self) -> list[str]:
        """Return appropriate template based on view_mode."""
        view_mode = self.request.GET.get('view_mode', 'week')
        if view_mode == 'month':
            return ['scheduling/partials/calendar_month_grid.html']
        return ['scheduling/partials/calendar_grid.html']

    def get_context_data(self, **kwargs):
        """
        Build the context dictionary for the calendar grid partial.

        Parses query parameters for date, direction, and view_mode,
        then calculates appropriate data based on the view mode.
        """
        context = super().get_context_data(**kwargs)

        # Detect if this is an HTMX request for conditional OOB rendering
        context['is_htmx'] = self.request.headers.get('HX-Request') == 'true'

        # Parse parameters from query string
        view_date = self._parse_view_date()
        direction = self.request.GET.get('direction', 'next')
        view_mode = self.request.GET.get('view_mode', 'week')

        # Determine shift visibility based on user role
        user = self.request.user
        published_only = not user.is_manager

        if view_mode == 'month':
            context.update(self._build_month_context(
                view_date, user, published_only, direction
            ))
        else:
            context.update(self._build_week_context(
                view_date, user, published_only, direction
            ))

        return context

    def _build_week_context(
        self,
        view_date: date,
        user,
        published_only: bool,
        direction: str,
    ) -> dict:
        """Build context data for week view mode."""
        week_start, week_end = CalendarService.get_week_range(view_date)
        week_dates = CalendarService.get_week_dates(view_date)

        shifts_by_date = CalendarService.get_shifts_for_range(
            week_start, week_end, user=user, published_only=published_only
        )
        day_offs_by_date = CalendarService.get_day_offs_for_range(
            week_start, week_end, user=user
        )

        prev_week = (week_start - timedelta(days=7)).isoformat()
        next_week = (week_start + timedelta(days=7)).isoformat()

        return {
            'view_date': view_date,
            'week_start': week_start,
            'week_end': week_end,
            'week_dates': week_dates,
            'shifts_by_date': shifts_by_date,
            'day_offs_by_date': day_offs_by_date,
            'prev_week': prev_week,
            'next_week': next_week,
            'prev_period': prev_week,
            'next_period': next_week,
            'today': date.today(),
            'direction': direction,
            'view_mode': 'week',
            'employees': User.objects.all(),
            'departments': Department.objects.all(),
        }

    def _build_month_context(
        self,
        view_date: date,
        user,
        published_only: bool,
        direction: str,
    ) -> dict:
        """Build context data for month view mode."""
        month_weeks = CalendarService.get_month_dates(view_date)
        first_of_month, last_of_month = CalendarService.get_month_range(view_date)

        # Get shifts for the entire grid (may span 3 months)
        grid_start = month_weeks[0][0]  # First Monday
        grid_end = month_weeks[-1][-1]  # Last Sunday

        shifts_by_date = CalendarService.get_shifts_for_range(
            grid_start, grid_end, user=user, published_only=published_only
        )
        day_offs_by_date = CalendarService.get_day_offs_for_range(
            grid_start, grid_end, user=user
        )

        # Calculate prev/next month navigation dates
        prev_month = (first_of_month - timedelta(days=1)).replace(day=1).isoformat()
        if view_date.month == 12:
            next_month_date = view_date.replace(year=view_date.year + 1, month=1, day=1)
        else:
            next_month_date = view_date.replace(month=view_date.month + 1, day=1)
        next_month = next_month_date.isoformat()

        return {
            'view_date': view_date,
            'month_weeks': month_weeks,
            'current_month': view_date.month,
            'current_year': view_date.year,
            'shifts_by_date': shifts_by_date,
            'day_offs_by_date': day_offs_by_date,
            'prev_period': prev_month,
            'next_period': next_month,
            'today': date.today(),
            'direction': direction,
            'view_mode': 'month',
            'day_names': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            'employees': User.objects.all(),
            'departments': Department.objects.all(),
        }

    def _parse_view_date(self) -> date:
        """
        Parse the date from query parameters.

        Returns:
            The parsed date, or today's date if parsing fails or no date provided.
        """
        date_str = self.request.GET.get('date')
        if date_str:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        return date.today()


# =============================================================================
# Shift CRUD Views
# =============================================================================


class ShiftFormPartial(ManagerRequiredMixin, TemplateView):
    """
    HTMX partial view for rendering the shift creation modal.

    Provides a shift creation form with the date pre-filled from query parameters.
    Used to dynamically load the form into the global modal via HTMX when clicking
    "Add Shift" buttons on day cells.

    Query Parameters:
        date (str, optional): Date in YYYY-MM-DD format to pre-fill the date field.

    Context Variables:
        form_date: The date for the new shift (date object).
        employees: QuerySet of all User objects for employee selection.
        departments: QuerySet of all Department objects.
    """

    template_name = 'modals/shift_create.html'

    def get_context_data(self, **kwargs):
        """Build context with form date and related data."""
        context = super().get_context_data(**kwargs)

        # Get initial date from query parameter
        date_str = self.request.GET.get('date')
        if date_str:
            try:
                context['form_date'] = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                context['form_date'] = date.today()
        else:
            context['form_date'] = date.today()

        context['employees'] = User.objects.all()
        context['departments'] = Department.objects.all()
        context['form'] = ShiftForm()

        return context


class PublishConfirmView(ManagerRequiredMixin, TemplateView):
    """Render the publish confirmation modal."""
    template_name = 'modals/publish_confirm.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['start_date'] = self.request.GET.get('start')
        context['end_date'] = self.request.GET.get('end')
        return context


class ShiftCreateView(ManagerRequiredMixin, CreateView):
    """
    View for creating new shifts.

    Handles POST requests to create a new shift. On success, returns an
    HTMX response with appropriate triggers for frontend updates.

    Attributes:
        model: Shift model.
        form_class: ShiftForm for validation.
        template_name: Partial template for form rendering.

    HTMX Response:
        On success, returns HttpResponse with HX-Trigger header containing
        'shift-created' event to notify frontend of the new shift.
    """

    model = Shift
    form_class = ShiftForm
    template_name = 'scheduling/partials/shift_form.html'

    def get_context_data(self, **kwargs):
        """Add employees and departments to context."""
        context = super().get_context_data(**kwargs)
        context['employees'] = User.objects.all()
        context['departments'] = Department.objects.all()
        return context

    def form_valid(self, form):
        """
        Handle valid form submission.

        Sets the created_by field to the current user before saving,
        then returns an HTMX response with a trigger event.
        Sends email notification if shift is published on creation.
        """
        form.instance.created_by = self.request.user
        self.object = form.save()

        # Send email if shift is published on creation
        if self.object.published:
            EmailService.send_shift_assigned(self.object)
            NotificationService.create(
                recipient=self.object.employee,
                message=f"New shift assigned: {self.object.date.strftime('%A, %b %d')} ({self.object.start_time.strftime('%I:%M %p')} - {self.object.end_time.strftime('%I:%M %p')})",
                link=f"/"
            )

        # Render success state template
        html = render_to_string(
            'modals/success_state.html',
            {
                'title': 'Shift Created!',
                'message': f"Shift for {self.object.employee.get_full_name() or self.object.employee.username} has been scheduled."
            },
            request=self.request
        )

        response = HttpResponse(html)
        # Signal calendar refresh (modal closes via Alpine.js after animation)
        response['HX-Trigger'] = 'shiftCreated'
        return response

    def form_invalid(self, form):
        """
        Handle invalid form submission for HTMX requests.

        Re-renders the modal template with form errors so users
        can see validation messages and correct their input.
        """
        context = self.get_context_data(form=form)
        context['form_date'] = self.request.POST.get('date')

        html = render_to_string(
            'modals/shift_create.html',
            context,
            request=self.request
        )
        return HttpResponse(html)


class ShiftDetailView(LoginRequiredMixin, DetailView):
    """
    View for displaying shift details.

    Shows detailed information about a specific shift. Available to
    all authenticated users, with is_manager flag in context for
    conditional rendering of edit/delete actions.

    Attributes:
        model: Shift model.
        template_name: Modal template for shift details.

    Context Variables:
        object: The Shift instance.
        is_manager: Boolean indicating if current user is a manager.
    """

    model = Shift
    template_name = 'modals/shift_detail.html'

    def get_context_data(self, **kwargs):
        """Add ownership and permission flags to context."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        shift = self.object
        context['is_manager'] = user.is_manager
        context['is_own_shift'] = (shift.employee_id == user.id)
        context['can_view_full_details'] = user.is_manager or context['is_own_shift']
        return context


class ShiftUpdateView(ManagerRequiredMixin, UpdateView):
    """
    View for editing existing shifts.

    Handles GET requests to display the edit form and POST requests
    to save changes. On success, dispatches a 'close-modal' event
    and returns the updated shift card HTML.

    Attributes:
        model: Shift model.
        form_class: ShiftForm for validation.
        template_name: Modal template for shift editing.

    HTMX Response:
        On success, returns updated shift card HTML with HX-Trigger
        header containing 'close-modal' event.
    """

    model = Shift
    form_class = ShiftForm
    template_name = 'modals/shift_edit.html'

    def get_context_data(self, **kwargs):
        """Add employees and departments to context."""
        context = super().get_context_data(**kwargs)
        context['employees'] = User.objects.all()
        context['departments'] = Department.objects.all()
        return context

    def form_valid(self, form):
        """
        Handle valid form submission.

        Captures old shift data before saving, saves the updated shift,
        sends email notification if shift is/was published, and returns
        an HTMX response with the updated shift card and a close-modal trigger.
        """
        # Capture old data BEFORE save so we can show "changed from X to Y" in the email.
        # self.object still holds the original database values until form.save() is called.
        old_data = {
            'date': self.object.date,
            'start_time': self.object.start_time,
            'end_time': self.object.end_time,
        }
        was_published = self.object.published

        self.object = form.save()

        # Send notification if shift is currently published OR was previously published.
        # Why both conditions?
        # - If published now: employee needs to know their active schedule changed
        # - If was published: employee was already notified about the shift, so they need
        #   to know it was modified (even if it's now unpublished/cancelled)
        if self.object.published or was_published:
            EmailService.send_shift_changed(self.object, old_data)
            NotificationService.create(
                recipient=self.object.employee,
                message=f"Shift updated: {self.object.date.strftime('%A, %b %d')} ({self.object.start_time.strftime('%I:%M %p')} - {self.object.end_time.strftime('%I:%M %p')})",
                link=f"/"
            )

        # Render success state template
        html = render_to_string(
            'modals/success_state.html',
            {
                'title': 'Shift Updated!',
                'message': f"Changes for {self.object.employee.get_full_name() or self.object.employee.username}'s shift have been saved."
            },
            request=self.request
        )

        response = HttpResponse(html)
        # Signal calendar refresh (modal closes via Alpine.js after animation)
        response['HX-Trigger'] = 'shiftUpdated'
        return response

    def form_invalid(self, form):
        """Handle invalid form submission - re-render edit modal with errors."""
        context = self.get_context_data(form=form)
        html = render_to_string(
            'modals/shift_edit.html',
            context,
            request=self.request
        )
        return HttpResponse(html)


class ShiftDeleteView(ManagerRequiredMixin, DeleteView):
    """
    View for deleting shifts.

    Handles POST requests to delete a shift. No confirmation template
    is used; deletion is handled directly via POST.

    Attributes:
        model: Shift model.

    HTMX Response:
        On success, returns empty HttpResponse with 200 status and
        HX-Trigger header containing 'shift-deleted' event.
    """

    model = Shift
    template_name = 'modals/confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        """Handle DELETE request by delegating to post()."""
        return self.post(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Handle POST request to delete the shift.

        Captures shift data before deletion, sends email notification
        if shift was published, then returns an empty response with
        shift-deleted trigger for HTMX.
        """
        self.object = self.get_object()

        # Capture data before deletion for email notification
        was_published = self.object.published
        shift_data = {
            'employee_name': self.object.employee.get_full_name(),
            'date': self.object.date,
            'start_time': self.object.start_time,
            'end_time': self.object.end_time,
        }
        employee_email = self.object.employee.email

        self.object.delete()

        # Send email if shift was published
        if was_published:
            EmailService.send_shift_deleted(employee_email, shift_data)
            employee = User.objects.filter(email=employee_email).first()
            if employee:
                NotificationService.create(
                    recipient=employee,
                    message=f"Shift cancelled: {shift_data['date'].strftime('%A, %b %d')}",
                    link=""
                )

        response = HttpResponse(status=200)
        response['HX-Trigger'] = 'closeModal, shiftDeleted'
        return response


# =============================================================================
# Shift Publishing Views
# =============================================================================


class PublishShiftsView(ManagerRequiredMixin, View):
    """
    Bulk publish shifts for a date range.

    Allows managers to publish multiple unpublished shifts at once,
    either by specifying a list of shift IDs or a date range.

    POST Parameters:
        shift_ids (list, optional): List of specific shift IDs to publish.
        start_date (str): Start date in YYYY-MM-DD format (used if shift_ids not provided).
        end_date (str): End date in YYYY-MM-DD format (used if shift_ids not provided).

    HTMX Response:
        Returns a success message with the count of published shifts.
        Includes 'HX-Trigger: shifts-published' header for frontend updates.
    """

    def post(self, request):
        """
        Handle POST request to bulk publish shifts.

        If shift_ids are provided, publishes those specific shifts.
        Otherwise, publishes all unpublished shifts in the date range.
        After publishing, sends weekly schedule emails to affected employees.
        """
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        shift_ids = request.POST.getlist('shift_ids')

        if shift_ids:
            queryset = Shift.objects.filter(id__in=shift_ids, published=False)
        else:
            queryset = Shift.objects.filter(
                date__gte=start_date,
                date__lte=end_date,
                published=False
            )

        # Capture shift IDs BEFORE the bulk update because update() returns count, not objects.
        # We need these IDs to re-fetch the shifts with related data for email notifications.
        affected_shift_ids = list(queryset.values_list('id', flat=True))

        count = queryset.update(published=True)

        # Send emails to affected employees if shifts were published
        if count > 0 and affected_shift_ids:
            # Re-fetch shifts with select_related to avoid N+1 queries when accessing employee data
            published_shifts = Shift.objects.filter(
                id__in=affected_shift_ids
            ).select_related('employee')

            # Group shifts by employee ID for batched email sending. This strategy:
            # 1. Sends ONE email per employee with ALL their shifts (not one email per shift)
            # 2. Reduces email volume and provides better UX (single consolidated schedule)
            # 3. Uses employee.id as key to handle multiple shifts for same employee
            shifts_by_employee = {}
            employees = set()
            for shift in published_shifts:
                employees.add(shift.employee)
                if shift.employee.id not in shifts_by_employee:
                    shifts_by_employee[shift.employee.id] = []
                shifts_by_employee[shift.employee.id].append(shift)

            # Determine the actual date range from published shifts for accurate email subject
            # (may differ from requested range if some dates had no unpublished shifts)
            if published_shifts:
                all_dates = [s.date for s in published_shifts]
                email_start_date = min(all_dates)
                email_end_date = max(all_dates)

                EmailService.send_week_published(
                    list(employees),
                    email_start_date,
                    email_end_date,
                    shifts_by_employee
                )

                # Create in-app notifications for each employee with shift count for quick reference
                for employee in employees:
                    employee_shifts = shifts_by_employee.get(employee.id, [])
                    if employee_shifts:
                        NotificationService.create(
                            recipient=employee,
                            message=f"Your schedule has been published: {email_start_date.strftime('%b %d')} - {email_end_date.strftime('%b %d')} ({len(employee_shifts)} shift{'s' if len(employee_shifts) > 1 else ''})",
                            link="/"
                        )

        response = HttpResponse(f'{count} shift{"s" if count != 1 else ""} published')
        response['HX-Trigger'] = 'closeModal, shiftUpdated'
        return response


class ShiftPublishToggleView(ManagerRequiredMixin, View):
    """
    Toggle the published status of a single shift.

    Allows managers to quickly publish or unpublish individual shifts
    directly from the shift card without opening a modal.

    URL Parameters:
        pk (int): Primary key of the shift to toggle.

    HTMX Response:
        Returns the updated shift card HTML for in-place replacement.
        Includes 'HX-Trigger: shift-toggled' header for frontend updates.
    """

    def post(self, request, pk):
        """
        Handle POST request to toggle shift published status.

        Flips the published boolean, sends email notification if
        toggling to published, and returns the updated shift card.
        """
        shift = get_object_or_404(Shift, pk=pk)
        was_published = shift.published
        shift.published = not shift.published
        shift.save(update_fields=['published'])

        # Send email if toggled to published
        if shift.published and not was_published:
            EmailService.send_shift_assigned(shift)
            NotificationService.create(
                recipient=shift.employee,
                message=f"New shift published: {shift.date.strftime('%A, %b %d')} ({shift.start_time.strftime('%I:%M %p')} - {shift.end_time.strftime('%I:%M %p')})",
                link=f"/"
            )

        html = render_to_string(
            'scheduling/partials/shift_card.html',
            {'shift': shift, 'is_manager': request.user.is_manager, 'today': date.today()},
            request=request
        )

        response = HttpResponse(html)
        response['HX-Trigger'] = 'closeModal, shiftUpdated'
        return response


# =============================================================================
# Day-Off Request Views
# =============================================================================


class DayOffRequestListView(LoginRequiredMixin, ListView):
    """
    List day-off requests.

    Managers see all requests, employees see only their own.
    Supports filtering by status via query parameter.

    Query Parameters:
        status (str, optional): Filter by request status ('pending', 'approved',
            'denied', or 'all'). Defaults to 'all'.

    Context Variables:
        requests: QuerySet of DayOffRequest objects.
        is_manager: Boolean indicating if current user is a manager.
        current_status: The currently selected status filter.
    """

    model = DayOffRequest
    template_name = 'scheduling/dayoff_list.html'
    context_object_name = 'requests'

    def get_queryset(self):
        """
        Build the queryset for day-off requests.

        Managers see all requests; employees see only their own.
        Filters by status if provided in query parameters.
        """
        queryset = DayOffRequest.objects.select_related('employee', 'reviewed_by')

        # Filter by role
        if not self.request.user.is_manager:
            queryset = queryset.filter(employee=self.request.user)

        # Filter by status if provided
        status = self.request.GET.get('status')
        if status and status != 'all':
            queryset = queryset.filter(status=status)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        """Add is_manager flag and current status filter to context."""
        context = super().get_context_data(**kwargs)
        context['is_manager'] = self.request.user.is_manager
        context['current_status'] = self.request.GET.get('status', 'all')
        return context


class DayOffRequestDetailView(LoginRequiredMixin, DetailView):
    """
    View single day-off request details.

    Managers can view any request; employees can only view their own.

    Context Variables:
        dayoff: The DayOffRequest object.
        is_manager: Boolean indicating if current user is a manager.
    """

    model = DayOffRequest
    template_name = 'modals/dayoff_detail.html'
    context_object_name = 'dayoff'

    def get_queryset(self):
        """
        Build the queryset for day-off request detail.

        Managers can view any request; employees can view their own plus
        others' approved requests.
        """
        from django.db.models import Q

        queryset = DayOffRequest.objects.select_related('employee', 'reviewed_by')
        if not self.request.user.is_manager:
            # Employees can view their own + others' approved
            queryset = queryset.filter(
                Q(employee=self.request.user) | Q(status=DayOffRequest.Status.APPROVED)
            )
        return queryset

    def get_context_data(self, **kwargs):
        """Add ownership and permission flags to context."""
        context = super().get_context_data(**kwargs)
        context['is_manager'] = self.request.user.is_manager
        context['is_own_request'] = (self.object.employee_id == self.request.user.id)
        return context


class DayOffRequestUpdateView(LoginRequiredMixin, UpdateView):
    """
    View for editing a pending day-off request.

    Only the employee who created the request can edit it,
    and only while it's still pending (not approved/denied).
    """
    model = DayOffRequest
    form_class = DayOffRequestForm
    template_name = 'modals/dayoff_edit.html'
    context_object_name = 'dayoff'

    def get_queryset(self):
        """Only allow editing own pending requests."""
        return DayOffRequest.objects.filter(
            employee=self.request.user,
            status=DayOffRequest.Status.PENDING
        )

    def form_valid(self, form):
        """Handle successful form submission."""
        self.object = form.save()
        response = HttpResponse()
        response['HX-Trigger'] = 'closeModal, shiftUpdated'
        return response

    def form_invalid(self, form):
        """Handle invalid form submission for HTMX requests."""
        context = self.get_context_data(form=form)
        html = render_to_string(self.template_name, context, request=self.request)
        return HttpResponse(html)


class DayOffRequestCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new day-off request.

    Handles POST requests to create a new day-off request.
    Automatically assigns the current user as the employee.

    HTMX Response:
        On success, returns HttpResponse with HX-Trigger header containing
        'closeModal, requestCreated' events.
    """

    model = DayOffRequest
    form_class = DayOffRequestForm
    template_name = 'modals/dayoff_form.html'

    def form_valid(self, form):
        """
        Handle valid form submission.

        Sets the employee field to the current user before saving,
        sends email notification to managers, then returns an HTMX
        response with trigger events.
        """
        form.instance.employee = self.request.user
        self.object = form.save()

        # Send email to managers
        EmailService.send_dayoff_submitted(self.object)

        # Create notifications for all managers
        managers = User.objects.filter(role=User.Role.MANAGER)
        employee_name = self.object.employee.get_full_name() or self.object.employee.username
        for manager in managers:
            NotificationService.create(
                recipient=manager,
                message=f"New day-off request from {employee_name}: {self.object.start_date.strftime('%b %d')} - {self.object.end_date.strftime('%b %d')}",
                link=f"/requests/"
            )

        # Render success state template
        html = render_to_string(
            'modals/success_state.html',
            {
                'title': 'Request Submitted!',
                'message': f"Your time off request for {self.object.start_date.strftime('%b %d')} - {self.object.end_date.strftime('%b %d')} has been submitted."
            },
            request=self.request
        )

        response = HttpResponse(html)
        # Signal list refresh (modal closes via Alpine.js after animation)
        response['HX-Trigger'] = 'requestCreated'
        return response

    def form_invalid(self, form):
        """
        Handle invalid form submission for HTMX requests.

        Re-renders the modal template with form errors so users
        can see validation messages and correct their input.
        """
        context = self.get_context_data(form=form)
        html = render_to_string(self.template_name, context, request=self.request)
        return HttpResponse(html)


class DayOffRequestCancelView(LoginRequiredMixin, View):
    """
    Cancel own pending day-off request.

    Allows employees to cancel their own pending requests.
    Only pending requests can be cancelled.

    HTMX Response:
        On success, returns HttpResponse with HX-Trigger header containing
        'requestCancelled' event.
    """

    def post(self, request, pk):
        """
        Handle POST request to cancel a day-off request.

        Only allows cancelling own pending requests.
        """
        dayoff_request = get_object_or_404(
            DayOffRequest,
            pk=pk,
            employee=request.user,
            status=DayOffRequest.Status.PENDING
        )
        dayoff_request.delete()

        response = HttpResponse(status=200)
        response['HX-Trigger'] = 'closeModal, shiftUpdated'
        return response


class DayOffRequestApproveView(ManagerRequiredMixin, View):
    """
    Approve a pending day-off request.

    Only managers can approve requests. Only pending requests
    can be approved.

    HTMX Response:
        Returns the updated request row HTML for in-place replacement.
    """

    def post(self, request, pk):
        """
        Handle POST request to approve a day-off request.

        Updates the request status, records the reviewer, sends email
        notification to employee, and returns the updated row for
        HTMX replacement.
        """
        dayoff_request = get_object_or_404(
            DayOffRequest,
            pk=pk,
            status=DayOffRequest.Status.PENDING
        )

        dayoff_request.status = DayOffRequest.Status.APPROVED
        dayoff_request.reviewed_by = request.user
        dayoff_request.reviewed_at = timezone.now()
        dayoff_request.save()

        # Send email to employee
        EmailService.send_dayoff_approved(dayoff_request, request.user)

        # Create notification for employee
        NotificationService.create(
            recipient=dayoff_request.employee,
            message=f"Your day-off request was approved: {dayoff_request.start_date.strftime('%b %d')} - {dayoff_request.end_date.strftime('%b %d')}",
            link=f"/requests/"
        )

        # Return updated row for HTMX
        html = render_to_string(
            'scheduling/partials/request_row.html',
            {'dayoff': dayoff_request, 'is_manager': True},
            request=request
        )
        response = HttpResponse(html)
        response['HX-Trigger'] = 'closeModal, requestUpdated'
        return response


class DayOffRequestDenyView(ManagerRequiredMixin, View):
    """
    Deny a pending day-off request.

    Only managers can deny requests. Only pending requests
    can be denied.

    HTMX Response:
        Returns the updated request row HTML for in-place replacement.
    """

    def post(self, request, pk):
        """
        Handle POST request to deny a day-off request.

        Updates the request status, records the reviewer, sends email
        notification to employee, and returns the updated row for
        HTMX replacement.
        """
        dayoff_request = get_object_or_404(
            DayOffRequest,
            pk=pk,
            status=DayOffRequest.Status.PENDING
        )

        dayoff_request.status = DayOffRequest.Status.DENIED
        dayoff_request.reviewed_by = request.user
        dayoff_request.reviewed_at = timezone.now()
        dayoff_request.save()

        # Send email to employee
        EmailService.send_dayoff_denied(dayoff_request, request.user)

        # Create notification for employee
        NotificationService.create(
            recipient=dayoff_request.employee,
            message=f"Your day-off request was denied: {dayoff_request.start_date.strftime('%b %d')} - {dayoff_request.end_date.strftime('%b %d')}",
            link=f"/requests/"
        )

        # Return updated row for HTMX
        html = render_to_string(
            'scheduling/partials/request_row.html',
            {'dayoff': dayoff_request, 'is_manager': True},
            request=request
        )
        response = HttpResponse(html)
        response['HX-Trigger'] = 'closeModal, requestUpdated'
        return response


class DayOffFormPartial(LoginRequiredMixin, TemplateView):
    """
    HTMX partial for day-off request form modal.

    Provides a day-off request creation form for loading into the
    global modal via HTMX.

    Context Variables:
        form: DayOffRequestForm instance.
    """

    template_name = 'modals/dayoff_form.html'

    def get_context_data(self, **kwargs):
        """Add the form to context."""
        context = super().get_context_data(**kwargs)
        context['form'] = DayOffRequestForm()
        return context


class DayOffRequestListPartial(LoginRequiredMixin, TemplateView):
    """
    HTMX partial view for day-off requests list content.

    Used for polling to auto-refresh the requests list when
    status changes occur. Supports the same filtering as the
    main list view.

    Query Parameters:
        status (str, optional): Filter by request status ('pending',
            'approved', 'denied', or 'all'). Defaults to 'all'.

    Context Variables:
        requests: QuerySet of DayOffRequest objects.
        is_manager: Boolean indicating if current user is a manager.
    """

    template_name = 'scheduling/partials/dayoff_list_content.html'

    def get_context_data(self, **kwargs):
        """Build context with filtered requests."""
        context = super().get_context_data(**kwargs)

        # Build queryset with same logic as DayOffRequestListView
        queryset = DayOffRequest.objects.select_related('employee', 'reviewed_by')

        # Filter by role: managers see all, employees see only their own
        if not self.request.user.is_manager:
            queryset = queryset.filter(employee=self.request.user)

        # Filter by status if provided
        status = self.request.GET.get('status')
        if status and status != 'all':
            queryset = queryset.filter(status=status)

        context['requests'] = queryset.order_by('-created_at')
        context['is_manager'] = self.request.user.is_manager

        return context


# =============================================================================
# Notification Views
# =============================================================================


class NotificationBellPartial(LoginRequiredMixin, TemplateView):
    """
    HTMX partial view for the notification bell dropdown.

    Renders the notification bell dropdown content with recent
    notifications and unread count. Used for dynamic loading
    via HTMX when clicking the notification bell icon.

    Context Variables:
        notifications: List of recent Notification instances.
        unread_count: Number of unread notifications.
    """

    template_name = 'scheduling/partials/notification_bell.html'

    def get_context_data(self, **kwargs):
        """Build context with recent notifications and unread count."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['notifications'] = NotificationService.get_recent(user, limit=5)
        context['unread_count'] = NotificationService.get_unread_count(user)
        return context


class NotificationListView(LoginRequiredMixin, ListView):
    """
    Full page view for listing all user notifications.

    Displays a paginated list of all notifications for the
    authenticated user, ordered by creation date (newest first).

    Context Variables:
        notifications: QuerySet of Notification objects.
        unread_count: Number of unread notifications.
    """

    model = Notification
    template_name = 'scheduling/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        """Return notifications for the current user."""
        return Notification.objects.filter(
            recipient=self.request.user
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        """Add unread count to context."""
        context = super().get_context_data(**kwargs)
        context['unread_count'] = NotificationService.get_unread_count(self.request.user)
        return context


class MarkNotificationsReadView(LoginRequiredMixin, View):
    """
    Mark all notifications as read for the current user.

    Handles POST requests to mark all unread notifications as read.
    Returns an empty response with appropriate HTMX trigger headers.

    HTMX Response:
        On success, returns HttpResponse with HX-Trigger header
        containing 'notificationsRead' event.
    """

    def post(self, request):
        """
        Handle POST request to mark all notifications as read.

        Delegates to NotificationService.mark_all_read() and returns
        an empty response with HTMX trigger for frontend updates.
        """
        NotificationService.mark_all_read(request.user)

        response = HttpResponse(status=200)
        response['HX-Trigger'] = 'notificationsRead'
        return response


class NotificationCountView(LoginRequiredMixin, View):
    """
    Return the unread notification count as JSON.

    Provides a lightweight endpoint for polling the unread
    notification count without loading full notification data.

    Response:
        JSON object with 'count' key containing the unread count.

    Example Response:
        {"count": 5}
    """

    def get(self, request):
        """
        Handle GET request for unread notification count.

        Returns a JSON response with the count of unread notifications.
        """
        count = NotificationService.get_unread_count(request.user)
        return JsonResponse({'count': count})


class NotificationClickView(LoginRequiredMixin, View):
    """
    Handle notification click: mark as read and redirect.

    When a user clicks a notification, this view marks it as read
    and redirects to the notification's associated link. If no link
    is provided, redirects to the notification list page.

    URL Parameters:
        pk (int): Primary key of the notification to mark as read.

    HTMX Response:
        Returns a redirect response (HX-Redirect header for HTMX requests)
        to the notification's link or the notification list page.
    """

    def get(self, request, pk):
        """
        Handle GET request to mark notification as read and redirect.

        Marks the specified notification as read (if it belongs to the
        current user), then redirects to the notification's link or
        the notification list page.
        """
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        NotificationService.mark_as_read(pk, request.user)

        redirect_url = notification.link if notification.link else '/notifications/'

        # Support HTMX redirect
        if request.headers.get('HX-Request') == 'true':
            response = HttpResponse(status=200)
            response['HX-Redirect'] = redirect_url
            return response

        from django.shortcuts import redirect
        return redirect(redirect_url)


# =============================================================================
# Profile Management Views
# =============================================================================


class ProfileView(LoginRequiredMixin, TemplateView):
    """
    Display the user's profile page.

    Shows the current user's profile information with options to
    edit profile details and change password via modal forms.

    Context Variables:
        user: The current authenticated user.
    """

    template_name = 'scheduling/profile.html'


class ProfileEditView(LoginRequiredMixin, View):
    """
    Handle profile editing via HTMX modal.

    GET: Returns the profile edit form partial for the modal.
    POST: Processes the profile update and returns success/error response.

    HTMX Response:
        On success, returns success state with HX-Trigger for page refresh.
        On error, re-renders the form with validation errors.
    """

    def get(self, request):
        """
        Handle GET request to display the profile edit form.

        Returns the profile edit modal content with the form pre-filled
        with the current user's data.
        """
        form = UserProfileForm(instance=request.user)
        html = render_to_string(
            'modals/profile_edit.html',
            {'form': form},
            request=request
        )
        return HttpResponse(html)

    def post(self, request):
        """
        Handle POST request to update the user's profile.

        Validates the form data and updates the user's profile.
        Returns a success state on success or re-renders the form
        with errors on validation failure.
        """
        form = UserProfileForm(request.POST, instance=request.user)

        if form.is_valid():
            form.save()

            # Render success state
            html = render_to_string(
                'modals/success_state.html',
                {
                    'title': 'Profile Updated!',
                    'message': 'Your profile has been updated successfully.'
                },
                request=request
            )

            response = HttpResponse(html)
            response['HX-Trigger'] = 'profileUpdated'
            return response

        # Re-render form with errors
        html = render_to_string(
            'modals/profile_edit.html',
            {'form': form},
            request=request
        )
        return HttpResponse(html)


class PasswordChangeView(LoginRequiredMixin, View):
    """
    Handle password change via HTMX modal.

    GET: Returns the password change form partial for the modal.
    POST: Processes the password change and returns success/error response.

    HTMX Response:
        On success, returns success state with HX-Trigger for modal close.
        On error, re-renders the form with validation errors.
    """

    def get(self, request):
        """
        Handle GET request to display the password change form.

        Returns the password change modal content with an empty form.
        """
        form = PasswordChangeForm(user=request.user)
        html = render_to_string(
            'modals/password_change.html',
            {'form': form},
            request=request
        )
        return HttpResponse(html)

    def post(self, request):
        """
        Handle POST request to change the user's password.

        Validates the form data (old password verification, new password
        confirmation) and updates the user's password. Returns a success
        state on success or re-renders the form with errors on failure.
        """
        form = PasswordChangeForm(user=request.user, data=request.POST)

        if form.is_valid():
            # Update the password
            request.user.set_password(form.cleaned_data['new_password'])
            request.user.save()

            # Update session to prevent logout after password change
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)

            # Render success state
            html = render_to_string(
                'modals/success_state.html',
                {
                    'title': 'Password Changed!',
                    'message': 'Your password has been updated successfully.'
                },
                request=request
            )

            response = HttpResponse(html)
            response['HX-Trigger'] = 'passwordChanged'
            return response

        # Re-render form with errors
        html = render_to_string(
            'modals/password_change.html',
            {'form': form},
            request=request
        )
        return HttpResponse(html)


# =============================================================================
# Time Entry / Clock In-Out Views
# =============================================================================


class ClockInView(LoginRequiredMixin, View):
    """
    Clock in for a shift.

    Creates a new TimeEntry with the current time as clock_in.
    Only the shift owner can clock in, and only if not already clocked in.

    URL Parameters:
        pk (int): Primary key of the shift to clock in to.

    HTMX Response:
        Returns the updated clock button partial with HX-Trigger
        containing 'clockedIn' event for frontend updates.
    """

    def post(self, request, pk):
        """
        Handle POST request to clock in.

        Validates that the user owns the shift and isn't already clocked in,
        then creates a TimeEntry and returns the updated clock button.
        """
        from django.http import HttpResponseBadRequest, HttpResponseForbidden

        shift = get_object_or_404(Shift, pk=pk)

        # Verify user owns this shift
        if shift.employee != request.user:
            return HttpResponseForbidden("You can only clock in to your own shifts.")

        # Check if already clocked in
        if shift.active_time_entry:
            return HttpResponseBadRequest("Already clocked in to this shift.")

        # Create time entry
        TimeEntry.objects.create(
            shift=shift,
            employee=request.user,
            clock_in=timezone.now()
        )

        # Return updated clock button partial
        response = render(
            request,
            'scheduling/partials/clock_button.html',
            {'shift': shift, 'today': date.today()}
        )
        response['HX-Trigger'] = 'clockedIn'
        return response


class ClockOutView(LoginRequiredMixin, View):
    """
    Clock out from a shift.

    Updates the active TimeEntry with the current time as clock_out.
    Only the shift owner can clock out, and only if currently clocked in.

    URL Parameters:
        pk (int): Primary key of the shift to clock out from.

    HTMX Response:
        Returns the updated clock button partial with HX-Trigger
        containing 'clockedOut' event for frontend updates.
    """

    def post(self, request, pk):
        """
        Handle POST request to clock out.

        Validates that the user owns the shift and is clocked in,
        then updates the TimeEntry and returns the updated clock button.
        """
        from django.http import HttpResponseBadRequest, HttpResponseForbidden

        shift = get_object_or_404(Shift, pk=pk)

        # Verify user owns this shift
        if shift.employee != request.user:
            return HttpResponseForbidden("You can only clock out of your own shifts.")

        # Get active time entry
        entry = shift.active_time_entry
        if not entry:
            return HttpResponseBadRequest("Not clocked in to this shift.")

        # Update clock out time
        entry.clock_out = timezone.now()
        entry.save()

        # Return updated clock button partial
        response = render(
            request,
            'scheduling/partials/clock_button.html',
            {'shift': shift, 'today': date.today()}
        )
        response['HX-Trigger'] = 'clockedOut'
        return response


# =============================================================================
# Hours Dashboard Views
# =============================================================================


class HoursDashboardView(LoginRequiredMixin, TemplateView):
    """
    Display hours worked dashboard with scheduled vs actual hours.

    For employees: Shows their own hours for the week with daily breakdown.
    For managers: Shows all employees' hours with aggregate totals.

    Supports week navigation via URL parameter for viewing past/future weeks.

    URL Parameters:
        date_str (str, optional): Date in YYYY-MM-DD format to determine the week.
            Defaults to today's date if not provided or invalid.

    Context Variables:
        week_start: Monday of the displayed week.
        week_end: Sunday of the displayed week.
        prev_week: ISO date string for navigating to the previous week.
        next_week: ISO date string for navigating to the next week.
        is_manager: Boolean indicating if current user is a manager.

    For Employees:
        weekly_hours: Dictionary with daily breakdown and totals.

    For Managers:
        employee_hours: List of employee hour summaries.
        grand_total_scheduled: Total scheduled hours across all employees.
        grand_total_actual: Total actual hours across all employees.
        grand_total_variance: Overall variance (actual - scheduled).
    """

    template_name = 'scheduling/hours_dashboard.html'

    def get_context_data(self, **kwargs):
        """
        Build the context dictionary for the hours dashboard template.

        Parses the date_str from URL kwargs, calculates week boundaries,
        and retrieves appropriate hours data based on user role.
        """
        context = super().get_context_data(**kwargs)

        # Parse target date from URL or use today as default
        target_date = self._parse_target_date()

        # Calculate week boundaries
        week_start, week_end = HoursService.get_week_range(target_date)

        # Base context for navigation
        context['week_start'] = week_start
        context['week_end'] = week_end
        context['prev_week'] = (week_start - timedelta(days=7)).strftime('%Y-%m-%d')
        context['next_week'] = (week_start + timedelta(days=7)).strftime('%Y-%m-%d')
        context['is_manager'] = self.request.user.is_manager
        context['today'] = date.today()

        if self.request.user.is_manager:
            # Manager view: aggregate hours for all employees
            context['employee_hours'] = HoursService.get_all_employees_weekly_hours(week_start)

            # Calculate grand totals across all employees
            context['grand_total_scheduled'] = sum(
                e['scheduled'] for e in context['employee_hours']
            )
            context['grand_total_actual'] = sum(
                e['actual'] for e in context['employee_hours']
            )
            context['grand_total_variance'] = round(
                context['grand_total_actual'] - context['grand_total_scheduled'], 2
            )
        else:
            # Employee view: own hours with daily breakdown
            context['weekly_hours'] = HoursService.get_user_weekly_hours(
                self.request.user, week_start
            )

        return context

    def _parse_target_date(self) -> date:
        """
        Parse the date_str from URL kwargs.

        Returns:
            The parsed date, or today's date if parsing fails or no date provided.
        """
        date_str = self.kwargs.get('date_str')
        if date_str:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        return date.today()
