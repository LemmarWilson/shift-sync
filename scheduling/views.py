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
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views import View
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from .forms import DayOffRequestForm, ShiftForm
from .mixins import ManagerRequiredMixin
from .models import DayOffRequest, Department, Notification, Shift, User
from .services import CalendarService, EmailService, NotificationService


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

        # Render single shift card
        html = render_to_string(
            'scheduling/partials/shift_card.html',
            {'shift': self.object},
            request=self.request
        )

        response = HttpResponse(html)
        # Close modal via server-side trigger and signal calendar refresh
        response['HX-Trigger'] = 'closeModal, shiftCreated'
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
        """Add is_manager flag to context."""
        context = super().get_context_data(**kwargs)
        context['is_manager'] = self.request.user.is_manager
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
        # Capture old data before save for email notification
        old_data = {
            'date': self.object.date,
            'start_time': self.object.start_time,
            'end_time': self.object.end_time,
        }
        was_published = self.object.published

        self.object = form.save()

        # Send email if shift is/was published
        if self.object.published or was_published:
            EmailService.send_shift_changed(self.object, old_data)
            NotificationService.create(
                recipient=self.object.employee,
                message=f"Shift updated: {self.object.date.strftime('%A, %b %d')} ({self.object.start_time.strftime('%I:%M %p')} - {self.object.end_time.strftime('%I:%M %p')})",
                link=f"/"
            )

        # Render the updated shift card
        html = render_to_string(
            'scheduling/partials/shift_card.html',
            {'shift': self.object},
            request=self.request
        )

        response = HttpResponse(html)
        response['HX-Trigger'] = 'closeModal, shiftUpdated'
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

        # Capture shift IDs before update for email notifications
        affected_shift_ids = list(queryset.values_list('id', flat=True))

        count = queryset.update(published=True)

        # Send emails to affected employees if shifts were published
        if count > 0 and affected_shift_ids:
            # Re-fetch the now-published shifts with related data
            published_shifts = Shift.objects.filter(
                id__in=affected_shift_ids
            ).select_related('employee')

            # Group shifts by employee
            shifts_by_employee = {}
            employees = set()
            for shift in published_shifts:
                employees.add(shift.employee)
                if shift.employee.id not in shifts_by_employee:
                    shifts_by_employee[shift.employee.id] = []
                shifts_by_employee[shift.employee.id].append(shift)

            # Determine date range for email subject
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

                # Create notifications for each employee
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
            {'shift': shift, 'is_manager': request.user.is_manager},
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

        Managers can view any request; employees can only view their own.
        """
        queryset = DayOffRequest.objects.select_related('employee', 'reviewed_by')
        if not self.request.user.is_manager:
            queryset = queryset.filter(employee=self.request.user)
        return queryset

    def get_context_data(self, **kwargs):
        """Add is_manager flag to context."""
        context = super().get_context_data(**kwargs)
        context['is_manager'] = self.request.user.is_manager
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

        response = HttpResponse(status=200)
        response['HX-Trigger'] = 'closeModal, requestCreated'
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
