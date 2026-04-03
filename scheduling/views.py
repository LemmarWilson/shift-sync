"""
Views for the scheduling app.

This module contains class-based views for handling calendar and scheduling
HTTP requests. Views are organized by functionality:
- Calendar views for displaying shifts and time-off in weekly/monthly formats
- HTMX partial views for dynamic page updates
"""

from datetime import date, datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from .services import CalendarService


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
