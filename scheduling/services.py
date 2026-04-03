"""
Business logic services for the scheduling app.

This module contains service classes that encapsulate complex business logic,
keeping views thin and promoting code reuse. Services handle data aggregation,
filtering, and transformation for calendar and scheduling operations.
"""

import calendar
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from django.db.models import Q

from .models import DayOffRequest, Shift, User


class CalendarService:
    """
    Service class for calendar-related operations.

    Provides static methods for date range calculations and retrieving
    shifts and day-off requests organized by date. All methods are designed
    to handle edge cases gracefully and return appropriate empty collections
    when no data is found.
    """

    @staticmethod
    def get_week_range(target_date: date) -> tuple[date, date]:
        """
        Get the Monday-Sunday range for the week containing target_date.

        Args:
            target_date: Any date within the desired week.

        Returns:
            A tuple of (monday, sunday) dates for that week.

        Example:
            >>> CalendarService.get_week_range(date(2024, 3, 13))  # Wednesday
            (date(2024, 3, 11), date(2024, 3, 17))  # Mon-Sun
        """
        # weekday() returns 0 for Monday, 6 for Sunday
        days_since_monday = target_date.weekday()
        monday = target_date - timedelta(days=days_since_monday)
        sunday = monday + timedelta(days=6)
        return monday, sunday

    @staticmethod
    def get_week_dates(target_date: date) -> list[date]:
        """
        Get all seven dates (Monday-Sunday) for the week containing target_date.

        Args:
            target_date: Any date within the desired week.

        Returns:
            A list of 7 date objects from Monday to Sunday.

        Example:
            >>> CalendarService.get_week_dates(date(2024, 3, 13))
            [date(2024, 3, 11), date(2024, 3, 12), ..., date(2024, 3, 17)]
        """
        monday, _ = CalendarService.get_week_range(target_date)
        return [monday + timedelta(days=i) for i in range(7)]

    @staticmethod
    def get_month_dates(target_date: date) -> list[list[date]]:
        """
        Get a 6-week grid of dates for the month view calendar.

        Returns a list of 6 week lists (each containing 7 dates from Mon-Sun).
        Includes padding days from adjacent months to fill complete weeks.

        Args:
            target_date: Any date within the desired month.

        Returns:
            A list of 6 lists, each containing 7 date objects.

        Example:
            >>> CalendarService.get_month_dates(date(2024, 3, 15))
            [[date(2024, 2, 26), ..., date(2024, 3, 3)], ...]  # 6 weeks
        """
        # Get first day of month
        first_of_month = target_date.replace(day=1)

        # Find the Monday of the week containing the first day
        days_since_monday = first_of_month.weekday()
        start_date = first_of_month - timedelta(days=days_since_monday)

        # Generate 6 weeks (42 days) to cover all possible month layouts
        weeks = []
        current_date = start_date
        for _ in range(6):
            week = [current_date + timedelta(days=i) for i in range(7)]
            weeks.append(week)
            current_date += timedelta(days=7)

        return weeks

    @staticmethod
    def get_month_range(target_date: date) -> tuple[date, date]:
        """
        Get the first and last day of the month containing target_date.

        Args:
            target_date: Any date within the desired month.

        Returns:
            A tuple of (first_day, last_day) dates for that month.

        Example:
            >>> CalendarService.get_month_range(date(2024, 2, 15))
            (date(2024, 2, 1), date(2024, 2, 29))  # Leap year
        """
        first_day = target_date.replace(day=1)
        # Get the last day of the month using calendar.monthrange
        _, last_day_num = calendar.monthrange(target_date.year, target_date.month)
        last_day = target_date.replace(day=last_day_num)
        return first_day, last_day

    @staticmethod
    def get_shifts_for_range(
        start_date: date,
        end_date: date,
        user: Optional[User] = None,
        published_only: bool = False,
    ) -> dict[date, list[Shift]]:
        """
        Retrieve shifts within a date range, grouped by date.

        Filters shifts based on user role and publication status:
        - Managers see all shifts (published and unpublished)
        - Employees see published shifts plus their own unpublished shifts
        - If published_only=True, only published shifts are returned

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).
            user: The requesting user (for role-based filtering).
            published_only: If True, only return published shifts regardless of role.

        Returns:
            A dictionary mapping date objects to lists of Shift instances.
            Empty dates are not included in the dictionary.

        Example:
            >>> shifts = CalendarService.get_shifts_for_range(
            ...     date(2024, 3, 11),
            ...     date(2024, 3, 17),
            ...     user=employee_user
            ... )
            >>> shifts[date(2024, 3, 12)]
            [<Shift: John - 2024-03-12 (09:00-17:00)>]
        """
        # Base queryset filtered by date range
        queryset = Shift.objects.filter(
            date__gte=start_date,
            date__lte=end_date,
        ).select_related('employee', 'department')

        # Apply visibility filters based on user role and published_only flag
        if published_only:
            queryset = queryset.filter(published=True)
        elif user is not None and not user.is_manager:
            # Employees see: published shifts OR their own unpublished shifts
            queryset = queryset.filter(
                Q(published=True) | Q(employee=user)
            )
        # If user is a manager (and not published_only), they see all shifts

        # Group shifts by date
        shifts_by_date: dict[date, list[Shift]] = defaultdict(list)
        for shift in queryset.order_by('date', 'start_time'):
            shifts_by_date[shift.date].append(shift)

        return dict(shifts_by_date)

    @staticmethod
    def get_day_offs_for_range(
        start_date: date,
        end_date: date,
        user: Optional[User] = None,
    ) -> dict[date, list[DayOffRequest]]:
        """
        Retrieve approved day-off requests that overlap with a date range.

        For each approved request, includes all individual dates between the
        request's start_date and end_date that fall within the query range.

        Args:
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).
            user: Optional user to filter requests (currently unused but
                  included for future filtering capabilities).

        Returns:
            A dictionary mapping date objects to lists of DayOffRequest instances.
            A single request may appear in multiple dates if it spans multiple days.
            Empty dates are not included in the dictionary.

        Example:
            >>> # Request for March 11-13 (3 days off)
            >>> day_offs = CalendarService.get_day_offs_for_range(
            ...     date(2024, 3, 11),
            ...     date(2024, 3, 17)
            ... )
            >>> date(2024, 3, 12) in day_offs
            True
        """
        # Find approved requests that overlap with the query range
        # A request overlaps if: request.start_date <= end_date AND request.end_date >= start_date
        queryset = DayOffRequest.objects.filter(
            status=DayOffRequest.Status.APPROVED,
            start_date__lte=end_date,
            end_date__gte=start_date,
        ).select_related('employee')

        # Group by individual dates within the range
        day_offs_by_date: dict[date, list[DayOffRequest]] = defaultdict(list)

        for request in queryset:
            # Calculate the overlap between request dates and query range
            effective_start = max(request.start_date, start_date)
            effective_end = min(request.end_date, end_date)

            # Add the request to each date in the effective range
            current_date = effective_start
            while current_date <= effective_end:
                day_offs_by_date[current_date].append(request)
                current_date += timedelta(days=1)

        return dict(day_offs_by_date)
