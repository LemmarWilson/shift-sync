"""
Django admin configuration for the scheduling app.

Registers all models with the admin site and provides
customized admin interfaces for efficient data management.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import DayOffRequest, Department, Notification, Shift, TimeEntry, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin interface for the User model.

    Extends Django's built-in UserAdmin to include custom fields
    for role, department, phone, and color.
    """

    list_display = [
        'username',
        'email',
        'first_name',
        'last_name',
        'role',
        'department',
        'color_display',
        'is_active',
    ]
    list_filter = [
        'role',
        'department',
        'is_active',
        'is_staff',
        'date_joined',
    ]
    search_fields = [
        'username',
        'email',
        'first_name',
        'last_name',
        'phone',
    ]
    ordering = ['first_name', 'last_name']

    # Add custom fields to the fieldsets
    fieldsets = BaseUserAdmin.fieldsets + (
        ('ShiftSync Profile', {
            'fields': ('role', 'phone', 'color', 'department'),
        }),
    )

    # Add custom fields to the add form
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('ShiftSync Profile', {
            'fields': ('role', 'phone', 'color', 'department'),
        }),
    )

    @admin.display(description='Color')
    def color_display(self, obj: User) -> str:
        """Display the user's color as a colored box."""
        if obj.color:
            return format_html(
                '<span style="background-color: {}; padding: 2px 10px; '
                'border-radius: 3px; color: white;">{}</span>',
                obj.color,
                obj.color,
            )
        return '-'


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin interface for the Department model."""

    list_display = [
        'name',
        'manager',
        'employee_count',
        'created_at',
        'updated_at',
    ]
    list_filter = [
        'created_at',
        'updated_at',
    ]
    search_fields = [
        'name',
        'manager__username',
        'manager__first_name',
        'manager__last_name',
    ]
    raw_id_fields = ['manager']
    ordering = ['name']

    @admin.display(description='Employees')
    def employee_count(self, obj: Department) -> int:
        """Return the number of employees in the department."""
        return obj.employees.count()


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    """Admin interface for the Shift model."""

    list_display = [
        'employee',
        'department',
        'date',
        'start_time',
        'end_time',
        'published',
        'created_by',
        'created_at',
    ]
    list_filter = [
        'published',
        'department',
        'date',
        'created_at',
    ]
    search_fields = [
        'employee__username',
        'employee__first_name',
        'employee__last_name',
        'department__name',
        'notes',
    ]
    raw_id_fields = ['employee', 'department', 'created_by']
    date_hierarchy = 'date'
    ordering = ['-date', 'start_time']

    # Enable bulk actions
    actions = ['publish_shifts', 'unpublish_shifts']

    @admin.action(description='Publish selected shifts')
    def publish_shifts(self, request, queryset):
        """Mark selected shifts as published."""
        count = queryset.update(published=True)
        self.message_user(request, f'{count} shift(s) published successfully.')

    @admin.action(description='Unpublish selected shifts')
    def unpublish_shifts(self, request, queryset):
        """Mark selected shifts as unpublished."""
        count = queryset.update(published=False)
        self.message_user(request, f'{count} shift(s) unpublished successfully.')


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    """Admin interface for the TimeEntry model."""

    list_display = [
        'employee',
        'shift',
        'clock_in',
        'clock_out',
        'get_duration',
        'notes',
        'updated_at',
    ]
    list_filter = [
        'clock_in',
        'employee',
        'shift__department',
    ]
    search_fields = [
        'employee__username',
        'employee__first_name',
        'employee__last_name',
        'notes',
    ]
    raw_id_fields = ['shift', 'employee']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'clock_in'
    ordering = ['-clock_in']

    @admin.display(description='Duration')
    def get_duration(self, obj: TimeEntry) -> str:
        """Display the duration of the time entry."""
        if obj.duration_hours is not None:
            return f"{obj.duration_hours}h"
        return "In Progress"


@admin.register(DayOffRequest)
class DayOffRequestAdmin(admin.ModelAdmin):
    """Admin interface for the DayOffRequest model."""

    list_display = [
        'employee',
        'start_date',
        'end_date',
        'status',
        'reviewed_by',
        'reviewed_at',
        'created_at',
    ]
    list_filter = [
        'status',
        'start_date',
        'created_at',
    ]
    search_fields = [
        'employee__username',
        'employee__first_name',
        'employee__last_name',
        'reason',
    ]
    raw_id_fields = ['employee', 'reviewed_by']
    date_hierarchy = 'start_date'
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']

    # Enable bulk actions
    actions = ['approve_requests', 'deny_requests']

    @admin.action(description='Approve selected requests')
    def approve_requests(self, request, queryset):
        """Approve selected day-off requests."""
        from django.utils import timezone

        count = queryset.filter(status=DayOffRequest.Status.PENDING).update(
            status=DayOffRequest.Status.APPROVED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f'{count} request(s) approved successfully.')

    @admin.action(description='Deny selected requests')
    def deny_requests(self, request, queryset):
        """Deny selected day-off requests."""
        from django.utils import timezone

        count = queryset.filter(status=DayOffRequest.Status.PENDING).update(
            status=DayOffRequest.Status.DENIED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f'{count} request(s) denied successfully.')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for the Notification model."""

    list_display = [
        'recipient',
        'message_preview',
        'link',
        'read',
        'created_at',
    ]
    list_filter = [
        'read',
        'created_at',
    ]
    search_fields = [
        'recipient__username',
        'recipient__first_name',
        'recipient__last_name',
        'message',
    ]
    raw_id_fields = ['recipient']
    ordering = ['-created_at']
    readonly_fields = ['created_at']

    # Enable bulk actions
    actions = ['mark_as_read', 'mark_as_unread']

    @admin.display(description='Message')
    def message_preview(self, obj: Notification) -> str:
        """Return a truncated preview of the notification message."""
        if len(obj.message) > 50:
            return f'{obj.message[:50]}...'
        return obj.message

    @admin.action(description='Mark selected as read')
    def mark_as_read(self, request, queryset):
        """Mark selected notifications as read."""
        count = queryset.update(read=True)
        self.message_user(request, f'{count} notification(s) marked as read.')

    @admin.action(description='Mark selected as unread')
    def mark_as_unread(self, request, queryset):
        """Mark selected notifications as unread."""
        count = queryset.update(read=False)
        self.message_user(request, f'{count} notification(s) marked as unread.')
