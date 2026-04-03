"""
Business logic services for the scheduling app.

This module contains service classes that encapsulate complex business logic,
keeping views thin and promoting code reuse. Services handle data aggregation,
filtering, and transformation for calendar and scheduling operations.
"""

import calendar
import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import TYPE_CHECKING, Optional

from django.core.mail import send_mail
from django.db.models import Q
from django.template.loader import render_to_string

from .models import DayOffRequest, Notification, Shift, User

if TYPE_CHECKING:
    from .models import Shift as ShiftType

logger = logging.getLogger(__name__)


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

        # Group shifts by date and add ownership flag
        shifts_by_date: dict[date, list[Shift]] = defaultdict(list)
        for shift in queryset.order_by('date', 'start_time'):
            shift.is_own = (user is not None and shift.employee_id == user.id)
            shifts_by_date[shift.date].append(shift)

        return dict(shifts_by_date)

    @staticmethod
    def get_day_offs_for_range(
        start_date: date,
        end_date: date,
        user: Optional[User] = None,
    ) -> dict[date, list[DayOffRequest]]:
        """
        Retrieve approved and pending day-off requests that overlap with a date range.

        For each approved or pending request, includes all individual dates between the
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
        # Find approved and pending requests that overlap with the query range
        # A request overlaps if: request.start_date <= end_date AND request.end_date >= start_date
        queryset = DayOffRequest.objects.filter(
            status__in=[DayOffRequest.Status.APPROVED, DayOffRequest.Status.PENDING],
            start_date__lte=end_date,
            end_date__gte=start_date,
        ).select_related('employee')

        # Apply visibility filters based on user role
        # Managers see all approved + pending; employees see their own (pending + approved)
        # plus others' APPROVED only
        if user is not None and not user.is_manager:
            queryset = queryset.filter(
                Q(employee=user, status__in=[DayOffRequest.Status.APPROVED, DayOffRequest.Status.PENDING])
                | Q(status=DayOffRequest.Status.APPROVED)
            ).distinct()

        # Group by individual dates within the range
        day_offs_by_date: dict[date, list[DayOffRequest]] = defaultdict(list)

        for request in queryset:
            # Add ownership flag
            request.is_own = (user is not None and request.employee_id == user.id)
            # Calculate the overlap between request dates and query range
            effective_start = max(request.start_date, start_date)
            effective_end = min(request.end_date, end_date)

            # Add the request to each date in the effective range
            current_date = effective_start
            while current_date <= effective_end:
                day_offs_by_date[current_date].append(request)
                current_date += timedelta(days=1)

        return dict(day_offs_by_date)


class EmailService:
    """
    Service class for sending shift-related email notifications.

    Provides static methods for sending templated HTML emails to employees
    when their shifts are created, modified, deleted, or when weekly
    schedules are published. All methods handle exceptions gracefully
    and return success/failure status.
    """

    @staticmethod
    def send_shift_assigned(shift: 'ShiftType') -> bool:
        """
        Send notification when a shift is assigned and published.

        Args:
            shift: The Shift instance that was assigned to an employee.

        Returns:
            True if the email was sent successfully, False otherwise.

        Example:
            >>> shift = Shift.objects.get(pk=1)
            >>> EmailService.send_shift_assigned(shift)
            True
        """
        subject = f"New Shift: {shift.date.strftime('%A, %B %d')}"
        context = {
            'employee_name': shift.employee.first_name,
            'shift': shift,
            'date_formatted': shift.date.strftime('%A, %B %d, %Y'),
            'time_range': f"{shift.start_time.strftime('%I:%M %p')} - {shift.end_time.strftime('%I:%M %p')}",
        }
        return EmailService._send_email(
            subject, 'emails/shift_assigned.html', context, [shift.employee.email]
        )

    @staticmethod
    def send_shift_changed(shift: 'ShiftType', old_data: dict) -> bool:
        """
        Send notification when a published shift is modified.

        Args:
            shift: The Shift instance after modification.
            old_data: Dictionary containing previous shift data with keys:
                      'date', 'start_time', 'end_time'.

        Returns:
            True if the email was sent successfully, False otherwise.

        Example:
            >>> shift = Shift.objects.get(pk=1)
            >>> old_data = {'date': '2024-03-12', 'start_time': '09:00', 'end_time': '17:00'}
            >>> EmailService.send_shift_changed(shift, old_data)
            True
        """
        subject = f"Shift Updated: {shift.date.strftime('%A, %B %d')}"
        context = {
            'employee_name': shift.employee.first_name,
            'shift': shift,
            'old_data': old_data,
            'date_formatted': shift.date.strftime('%A, %B %d, %Y'),
            'time_range': f"{shift.start_time.strftime('%I:%M %p')} - {shift.end_time.strftime('%I:%M %p')}",
        }
        return EmailService._send_email(
            subject, 'emails/shift_changed.html', context, [shift.employee.email]
        )

    @staticmethod
    def send_shift_reminder(shift: 'ShiftType') -> bool:
        """
        Send a reminder email for an upcoming shift.

        Sends a friendly reminder to the employee about their shift
        scheduled for tomorrow.

        Args:
            shift: The Shift instance to send a reminder for.

        Returns:
            True if the email was sent successfully, False otherwise.

        Example:
            >>> shift = Shift.objects.get(pk=1)
            >>> EmailService.send_shift_reminder(shift)
            True
        """
        if not shift.employee.email:
            logger.warning(
                f"Cannot send shift reminder: employee {shift.employee} has no email"
            )
            return False

        subject = f"Reminder: You work tomorrow at {shift.start_time.strftime('%I:%M %p')}"
        context = {
            'employee_name': shift.employee.first_name or shift.employee.username,
            'shift': shift,
            'date_formatted': shift.date.strftime('%A, %B %d, %Y'),
            'time_range': (
                f"{shift.start_time.strftime('%I:%M %p')} - "
                f"{shift.end_time.strftime('%I:%M %p')}"
            ),
        }
        return EmailService._send_email(
            subject, 'emails/shift_reminder.html', context, [shift.employee.email]
        )

    @staticmethod
    def send_shift_deleted(employee_email: str, shift_data: dict) -> bool:
        """
        Send notification when a shift is deleted/cancelled.

        Args:
            employee_email: Email address of the affected employee.
            shift_data: Dictionary containing deleted shift information with keys:
                        'date' (date object), 'start_time' (time object),
                        'end_time' (time object), 'employee_name' (str, optional).

        Returns:
            True if the email was sent successfully, False otherwise.

        Example:
            >>> shift_data = {
            ...     'date': date(2024, 3, 12),
            ...     'start_time': time(9, 0),
            ...     'end_time': time(17, 0),
            ...     'employee_name': 'John'
            ... }
            >>> EmailService.send_shift_deleted('john@example.com', shift_data)
            True
        """
        subject = f"Shift Cancelled: {shift_data['date'].strftime('%A, %B %d')}"
        context = {
            'employee_name': shift_data.get('employee_name', 'Employee'),
            'shift_data': shift_data,
        }
        return EmailService._send_email(
            subject, 'emails/shift_deleted.html', context, [employee_email]
        )

    @staticmethod
    def send_week_published(
        employees: list,
        week_start: date,
        week_end: date,
        shifts_by_employee: dict,
    ) -> int:
        """
        Send weekly schedule to all affected employees.

        Iterates through all employees who have shifts in the published week
        and sends each a personalized email with their schedule.

        Args:
            employees: List of User instances to notify.
            week_start: The Monday of the published week.
            week_end: The Sunday of the published week.
            shifts_by_employee: Dictionary mapping employee IDs to lists of Shift instances.

        Returns:
            The count of successfully sent emails.

        Example:
            >>> employees = User.objects.filter(role='employee')
            >>> shifts_by_employee = {1: [shift1, shift2], 2: [shift3]}
            >>> EmailService.send_week_published(
            ...     employees, date(2024, 3, 11), date(2024, 3, 17), shifts_by_employee
            ... )
            2
        """
        sent_count = 0
        for employee in employees:
            employee_shifts = shifts_by_employee.get(employee.id, [])
            if employee_shifts:
                subject = (
                    f"Your Schedule: {week_start.strftime('%b %d')} - "
                    f"{week_end.strftime('%b %d')}"
                )
                context = {
                    'employee_name': employee.first_name,
                    'week_start': week_start,
                    'week_end': week_end,
                    'shifts': employee_shifts,
                }
                if EmailService._send_email(
                    subject, 'emails/week_published.html', context, [employee.email]
                ):
                    sent_count += 1
        return sent_count

    @staticmethod
    def _send_email(
        subject: str,
        template: str,
        context: dict,
        recipients: list,
    ) -> bool:
        """
        Internal helper to send templated HTML emails.

        Renders the specified template with the given context and sends it
        as an HTML email. Falls back to a plain text message for email
        clients that don't support HTML.

        Args:
            subject: Email subject line.
            template: Path to the Django template to render.
            context: Context dictionary for template rendering.
            recipients: List of recipient email addresses.

        Returns:
            True if the email was sent successfully, False otherwise.
        """
        try:
            html_message = render_to_string(template, context)
            send_mail(
                subject=subject,
                message='Please view this email in HTML format.',
                from_email=None,  # Uses DEFAULT_FROM_EMAIL from settings
                recipient_list=recipients,
                html_message=html_message,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {recipients}: {e}")
            return False

    @staticmethod
    def send_dayoff_submitted(dayoff_request) -> bool:
        """
        Send notification to all managers when a day-off request is submitted.

        Args:
            dayoff_request: The DayOffRequest instance that was submitted.

        Returns:
            True if at least one email was sent successfully, False otherwise.

        Example:
            >>> request = DayOffRequest.objects.get(pk=1)
            >>> EmailService.send_dayoff_submitted(request)
            True
        """
        managers = User.objects.filter(role=User.Role.MANAGER)
        employee_name = (
            dayoff_request.employee.get_full_name()
            or dayoff_request.employee.username
        )

        subject = f"New day-off request from {employee_name}"
        context = {
            'employee_name': employee_name,
            'start_date': dayoff_request.start_date,
            'end_date': dayoff_request.end_date,
            'reason': dayoff_request.reason,
        }

        sent_count = 0
        for manager in managers:
            if manager.email:
                if EmailService._send_email(
                    subject,
                    'emails/dayoff_submitted.html',
                    context,
                    [manager.email]
                ):
                    sent_count += 1

        return sent_count > 0

    @staticmethod
    def send_dayoff_approved(dayoff_request, reviewer) -> bool:
        """
        Send notification to employee when their day-off request is approved.

        Args:
            dayoff_request: The DayOffRequest instance that was approved.
            reviewer: The User who approved the request.

        Returns:
            True if the email was sent successfully, False otherwise.

        Example:
            >>> request = DayOffRequest.objects.get(pk=1)
            >>> EmailService.send_dayoff_approved(request, manager_user)
            True
        """
        if not dayoff_request.employee.email:
            return False

        subject = "Your day off was approved"
        context = {
            'employee_name': (
                dayoff_request.employee.first_name
                or dayoff_request.employee.username
            ),
            'start_date': dayoff_request.start_date,
            'end_date': dayoff_request.end_date,
            'reviewer_name': reviewer.get_full_name() or reviewer.username,
        }

        return EmailService._send_email(
            subject,
            'emails/dayoff_approved.html',
            context,
            [dayoff_request.employee.email]
        )

    @staticmethod
    def send_dayoff_denied(dayoff_request, reviewer) -> bool:
        """
        Send notification to employee when their day-off request is denied.

        Args:
            dayoff_request: The DayOffRequest instance that was denied.
            reviewer: The User who denied the request.

        Returns:
            True if the email was sent successfully, False otherwise.

        Example:
            >>> request = DayOffRequest.objects.get(pk=1)
            >>> EmailService.send_dayoff_denied(request, manager_user)
            True
        """
        if not dayoff_request.employee.email:
            return False

        subject = "Your day-off request was not approved"
        context = {
            'employee_name': (
                dayoff_request.employee.first_name
                or dayoff_request.employee.username
            ),
            'start_date': dayoff_request.start_date,
            'end_date': dayoff_request.end_date,
            'reviewer_name': reviewer.get_full_name() or reviewer.username,
        }

        return EmailService._send_email(
            subject,
            'emails/dayoff_denied.html',
            context,
            [dayoff_request.employee.email]
        )


class NotificationService:
    """
    Service class for managing in-app notifications.

    Provides static methods for creating notifications, retrieving unread counts,
    fetching recent notifications, and marking notifications as read. All methods
    handle exceptions gracefully and return appropriate default values on failure.
    """

    @staticmethod
    def create(recipient: 'User', message: str, link: str = '') -> bool:
        """
        Create a new notification for a user.

        Args:
            recipient: The User who will receive the notification.
            message: The notification message content.
            link: Optional URL to related content.

        Returns:
            True if the notification was created successfully, False otherwise.

        Example:
            >>> user = User.objects.get(pk=1)
            >>> NotificationService.create(user, "Your shift was updated", "/shifts/1/")
            True
        """
        try:
            Notification.objects.create(
                recipient=recipient,
                message=message,
                link=link
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create notification for {recipient}: {e}")
            return False

    @staticmethod
    def get_unread_count(user: 'User') -> int:
        """
        Get the count of unread notifications for a user.

        Args:
            user: The User to check for unread notifications.

        Returns:
            The number of unread notifications, or 0 on error.

        Example:
            >>> user = User.objects.get(pk=1)
            >>> NotificationService.get_unread_count(user)
            3
        """
        try:
            return Notification.objects.filter(recipient=user, read=False).count()
        except Exception as e:
            logger.error(f"Failed to get unread count for {user}: {e}")
            return 0

    @staticmethod
    def get_recent(user: 'User', limit: int = 5) -> list:
        """
        Get recent notifications for a user.

        Args:
            user: The User to fetch notifications for.
            limit: Maximum number of notifications to return (default 5).

        Returns:
            A list of Notification instances ordered by creation date (newest first),
            or an empty list on error.

        Example:
            >>> user = User.objects.get(pk=1)
            >>> notifications = NotificationService.get_recent(user, limit=10)
            >>> len(notifications) <= 10
            True
        """
        try:
            return list(Notification.objects.filter(recipient=user).order_by('-created_at')[:limit])
        except Exception as e:
            logger.error(f"Failed to get recent notifications for {user}: {e}")
            return []

    @staticmethod
    def mark_all_read(user: 'User') -> bool:
        """
        Mark all notifications as read for a user.

        Args:
            user: The User whose notifications should be marked as read.

        Returns:
            True if the operation was successful, False otherwise.

        Example:
            >>> user = User.objects.get(pk=1)
            >>> NotificationService.mark_all_read(user)
            True
        """
        try:
            Notification.objects.filter(recipient=user, read=False).update(read=True)
            return True
        except Exception as e:
            logger.error(f"Failed to mark notifications read for {user}: {e}")
            return False

    @staticmethod
    def mark_as_read(notification_id: int, user: 'User') -> bool:
        """
        Mark a specific notification as read.

        Only marks the notification if it belongs to the specified user,
        providing security against unauthorized access.

        Args:
            notification_id: The ID of the notification to mark as read.
            user: The User who owns the notification.

        Returns:
            True if the operation was successful, False otherwise.

        Example:
            >>> user = User.objects.get(pk=1)
            >>> NotificationService.mark_as_read(notification_id=42, user=user)
            True
        """
        try:
            Notification.objects.filter(id=notification_id, recipient=user).update(read=True)
            return True
        except Exception as e:
            logger.error(f"Failed to mark notification {notification_id} read: {e}")
            return False
