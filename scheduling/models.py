"""
Data models for the scheduling app.

This module defines the core database models for ShiftSync:
- User: Extended user model with role-based access
- Department: Organizational units for grouping employees
- Shift: Individual work shifts assigned to employees
- DayOffRequest: Employee requests for time off
- Notification: In-app notifications for users
"""

import random

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Extended user model for ShiftSync.

    Extends Django's AbstractUser to add role-based access control,
    department assignment, and visual identification via color coding.
    """

    class Role(models.TextChoices):
        """User role choices for access control."""

        MANAGER = 'manager', 'Manager'
        EMPLOYEE = 'employee', 'Employee'

    # Color palette for auto-assignment to users
    COLOR_PALETTE = [
        '#6366f1',  # Indigo
        '#8b5cf6',  # Violet
        '#ec4899',  # Pink
        '#f97316',  # Orange
        '#14b8a6',  # Teal
        '#22c55e',  # Green
        '#3b82f6',  # Blue
        '#f59e0b',  # Amber
    ]

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.EMPLOYEE,
        help_text='User role determines access permissions.',
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text='Contact phone number.',
    )
    color = models.CharField(
        max_length=7,
        default='',
        blank=True,
        help_text='Hex color code for calendar display (auto-assigned if empty).',
    )
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        help_text='Department this employee belongs to.',
    )

    # Auto timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['first_name', 'last_name']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    @property
    def is_manager(self) -> bool:
        """Check if the user has manager role."""
        return self.role == self.Role.MANAGER

    def save(self, *args, **kwargs):
        """
        Save the user instance.

        Auto-assigns a random color from the palette if not already set.
        """
        if not self.color:
            self.color = random.choice(self.COLOR_PALETTE)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """Return a human-readable representation of the user."""
        display_name = self.get_full_name() or self.username
        return f"{display_name} ({self.get_role_display()})"


class Department(models.Model):
    """
    Department model for organizing employees.

    Represents an organizational unit within the company.
    Each department can have a manager and multiple employees.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Unique department name.',
    )
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_departments',
        limit_choices_to={'role': 'manager'},
        help_text='Manager responsible for this department.',
    )

    # Auto timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'

    def __str__(self) -> str:
        """Return the department name."""
        return self.name


class Shift(models.Model):
    """
    Shift model representing a work shift.

    Represents a scheduled work period for an employee,
    including date, time range, and assignment details.
    """

    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shifts',
        help_text='Employee assigned to this shift.',
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shifts',
        help_text='Department this shift is associated with.',
    )
    date = models.DateField(
        db_index=True,
        help_text='Date of the shift.',
    )
    start_time = models.TimeField(
        help_text='Shift start time.',
    )
    end_time = models.TimeField(
        help_text='Shift end time.',
    )
    notes = models.TextField(
        blank=True,
        help_text='Additional notes or instructions for the shift.',
    )
    published = models.BooleanField(
        default=False,
        help_text='Whether this shift is visible to employees.',
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_shifts',
        help_text='Manager who created this shift.',
    )

    # Auto timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'start_time']
        unique_together = ['employee', 'date', 'start_time']
        verbose_name = 'Shift'
        verbose_name_plural = 'Shifts'

    @property
    def scheduled_hours(self) -> float:
        """
        Calculate scheduled hours from start_time and end_time.

        Returns:
            The scheduled duration in hours (rounded to 2 decimal places).
        """
        from datetime import datetime

        start = datetime.combine(self.date, self.start_time)
        end = datetime.combine(self.date, self.end_time)
        return round((end - start).total_seconds() / 3600, 2)

    @property
    def actual_hours(self) -> float:
        """
        Get total actual hours from completed time entries.

        Returns:
            The sum of all completed time entry durations (rounded to 2 decimal places).
        """
        total = 0
        for entry in self.time_entries.filter(clock_out__isnull=False):
            if entry.duration_hours:
                total += entry.duration_hours
        return round(total, 2)

    @property
    def active_time_entry(self):
        """
        Get the current active (clocked in) time entry if any.

        Returns:
            The active TimeEntry instance, or None if not currently clocked in.
        """
        return self.time_entries.filter(clock_out__isnull=True).first()

    def __str__(self) -> str:
        """Return a human-readable representation of the shift."""
        return f"{self.employee} - {self.date} ({self.start_time}-{self.end_time})"


class DayOffRequest(models.Model):
    """
    Day-off request model for time-off management.

    Represents an employee's request for time off,
    including the date range, reason, and approval status.
    """

    class Status(models.TextChoices):
        """Request status choices."""

        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        DENIED = 'denied', 'Denied'

    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='day_off_requests',
        help_text='Employee requesting time off.',
    )
    start_date = models.DateField(
        help_text='First day of requested time off.',
    )
    end_date = models.DateField(
        help_text='Last day of requested time off.',
    )
    reason = models.TextField(
        blank=True,
        help_text='Reason for the time-off request.',
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        help_text='Current status of the request.',
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_requests',
        help_text='Manager who reviewed this request.',
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the request was reviewed.',
    )

    # Auto timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Day Off Request'
        verbose_name_plural = 'Day Off Requests'
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')),
                name='end_date_gte_start_date',
            ),
        ]

    def __str__(self) -> str:
        """Return a human-readable representation of the request."""
        return f"{self.employee} - {self.start_date} to {self.end_date} ({self.get_status_display()})"


class TimeEntry(models.Model):
    """
    Time entry model for tracking actual clock in/out times.

    Represents an employee's actual work time for a specific shift,
    allowing comparison between scheduled and actual hours worked.
    """

    shift = models.ForeignKey(
        'Shift',
        on_delete=models.CASCADE,
        related_name='time_entries',
        help_text='The shift this time entry is associated with.',
    )
    employee = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='time_entries',
        help_text='The employee who clocked in/out.',
    )
    clock_in = models.DateTimeField(
        help_text='When the employee clocked in.',
    )
    clock_out = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the employee clocked out (null if still clocked in).',
    )
    notes = models.TextField(
        blank=True,
        help_text='Manager adjustment notes or comments.',
    )

    # Auto timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-clock_in']
        verbose_name = 'Time Entry'
        verbose_name_plural = 'Time Entries'

    @property
    def duration_hours(self) -> float | None:
        """
        Calculate actual hours worked.

        Returns:
            The duration in hours (rounded to 2 decimal places),
            or None if still clocked in.
        """
        if self.clock_out:
            delta = self.clock_out - self.clock_in
            return round(delta.total_seconds() / 3600, 2)
        return None

    @property
    def is_clocked_in(self) -> bool:
        """Check if currently clocked in (no clock_out time)."""
        return self.clock_out is None

    def __str__(self) -> str:
        """Return a human-readable representation of the time entry."""
        status = "In Progress" if self.is_clocked_in else f"{self.duration_hours}h"
        return f"{self.employee} - {self.clock_in.date()} ({status})"


class Notification(models.Model):
    """
    Notification model for in-app messaging.

    Represents a notification sent to a user,
    typically for shift updates, request approvals, etc.
    """

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text='User receiving this notification.',
    )
    message = models.CharField(
        max_length=255,
        help_text='Notification message content.',
    )
    link = models.CharField(
        max_length=255,
        blank=True,
        help_text='Optional URL to related content.',
    )
    read = models.BooleanField(
        default=False,
        help_text='Whether the notification has been read.',
    )

    # Auto timestamp (no updated_at needed for notifications)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self) -> str:
        """Return a truncated representation of the notification."""
        return f"{self.recipient}: {self.message[:50]}"
