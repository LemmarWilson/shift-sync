"""
URL configuration for the scheduling app.

This module defines URL patterns for calendar views, HTMX partials,
and shift CRUD operations. All URLs are namespaced under 'scheduling'
for reverse URL resolution.

URL Patterns:
    Calendar:
        /                           - Main calendar view (today's week)
        /calendar/                  - Alternate calendar URL
        /calendar/<view_date>/      - Calendar for a specific date's week
        /partials/calendar-grid/    - HTMX partial for week navigation

    Shifts:
        /shifts/create/             - Create a new shift
        /shifts/<pk>/               - View shift details
        /shifts/<pk>/edit/          - Edit a shift
        /shifts/<pk>/delete/        - Delete a shift
        /partials/shift-form/       - HTMX partial for shift form
"""

from django.urls import path

from . import views

app_name = 'scheduling'

urlpatterns = [
    # Main calendar view - displays week containing current date
    # Note: Root URL (/) is handled by LandingView in config/urls.py
    path('calendar/', views.CalendarView.as_view(), name='calendar'),

    # Calendar view for a specific date (YYYY-MM-DD format)
    path(
        'calendar/<str:view_date>/',
        views.CalendarView.as_view(),
        name='calendar_date',
    ),

    # HTMX partial endpoints - Calendar
    path(
        'partials/calendar-grid/',
        views.CalendarGridPartial.as_view(),
        name='partial_calendar_grid',
    ),

    # Shift CRUD endpoints
    path(
        'shifts/create/',
        views.ShiftCreateView.as_view(),
        name='shift_create',
    ),
    path(
        'shifts/<int:pk>/',
        views.ShiftDetailView.as_view(),
        name='shift_detail',
    ),
    path(
        'shifts/<int:pk>/edit/',
        views.ShiftUpdateView.as_view(),
        name='shift_update',
    ),
    path(
        'shifts/<int:pk>/delete/',
        views.ShiftDeleteView.as_view(),
        name='shift_delete',
    ),

    # HTMX partial endpoints - Shifts
    path(
        'partials/shift-form/',
        views.ShiftFormPartial.as_view(),
        name='shift_form_partial',
    ),

    # Time Entry / Clock In-Out endpoints
    path(
        'shifts/<int:pk>/clock-in/',
        views.ClockInView.as_view(),
        name='clock_in',
    ),
    path(
        'shifts/<int:pk>/clock-out/',
        views.ClockOutView.as_view(),
        name='clock_out',
    ),

    # Shift Publishing endpoints
    path(
        'shifts/publish/confirm/',
        views.PublishConfirmView.as_view(),
        name='publish_confirm',
    ),
    path(
        'shifts/publish/',
        views.PublishShiftsView.as_view(),
        name='shifts_publish',
    ),
    path(
        'shifts/<int:pk>/toggle-publish/',
        views.ShiftPublishToggleView.as_view(),
        name='shift_toggle_publish',
    ),

    # Day-Off Request endpoints
    path(
        'requests/',
        views.DayOffRequestListView.as_view(),
        name='dayoff_list',
    ),
    path(
        'requests/<int:pk>/',
        views.DayOffRequestDetailView.as_view(),
        name='dayoff_detail',
    ),
    path(
        'requests/<int:pk>/edit/',
        views.DayOffRequestUpdateView.as_view(),
        name='dayoff_edit',
    ),
    path(
        'requests/create/',
        views.DayOffRequestCreateView.as_view(),
        name='dayoff_create',
    ),
    path(
        'requests/<int:pk>/cancel/',
        views.DayOffRequestCancelView.as_view(),
        name='dayoff_cancel',
    ),
    path(
        'requests/<int:pk>/approve/',
        views.DayOffRequestApproveView.as_view(),
        name='dayoff_approve',
    ),
    path(
        'requests/<int:pk>/deny/',
        views.DayOffRequestDenyView.as_view(),
        name='dayoff_deny',
    ),

    # HTMX partial endpoints - Day-Off Requests
    path(
        'partials/dayoff-form/',
        views.DayOffFormPartial.as_view(),
        name='dayoff_form_partial',
    ),
    path(
        'partials/dayoff-list/',
        views.DayOffRequestListPartial.as_view(),
        name='dayoff_list_partial',
    ),

    # Notification endpoints
    path(
        'notifications/',
        views.NotificationListView.as_view(),
        name='notification_list',
    ),
    path(
        'notifications/<int:pk>/click/',
        views.NotificationClickView.as_view(),
        name='notification_click',
    ),
    path(
        'notifications/mark-read/',
        views.MarkNotificationsReadView.as_view(),
        name='notification_mark_read',
    ),
    path(
        'notifications/count/',
        views.NotificationCountView.as_view(),
        name='notification_count',
    ),

    # HTMX partial endpoints - Notifications
    path(
        'partials/notification-bell/',
        views.NotificationBellPartial.as_view(),
        name='notification_bell_partial',
    ),

    # Profile endpoints
    path(
        'profile/',
        views.ProfileView.as_view(),
        name='profile',
    ),
    path(
        'profile/edit/',
        views.ProfileEditView.as_view(),
        name='profile_edit',
    ),
    path(
        'profile/change-password/',
        views.PasswordChangeView.as_view(),
        name='password_change',
    ),

    # Hours Dashboard endpoints
    path(
        'hours/',
        views.HoursDashboardView.as_view(),
        name='hours_dashboard',
    ),
    path(
        'hours/<str:date_str>/',
        views.HoursDashboardView.as_view(),
        name='hours_dashboard_date',
    ),
]
