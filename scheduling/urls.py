"""
URL configuration for the scheduling app.

This module defines URL patterns for calendar views and HTMX partials.
All URLs are namespaced under 'scheduling' for reverse URL resolution.

URL Patterns:
    /                           - Main calendar view (today's week)
    /calendar/                  - Alternate calendar URL
    /calendar/<view_date>/      - Calendar for a specific date's week
    /partials/calendar-grid/    - HTMX partial for week navigation
"""

from django.urls import path

from . import views

app_name = 'scheduling'

urlpatterns = [
    # Main calendar view - displays week containing current date
    path('', views.CalendarView.as_view(), name='calendar'),

    # Alternate URL for calendar (more explicit)
    path('calendar/', views.CalendarView.as_view(), name='calendar_alt'),

    # Calendar view for a specific date (YYYY-MM-DD format)
    path(
        'calendar/<str:view_date>/',
        views.CalendarView.as_view(),
        name='calendar_date',
    ),

    # HTMX partial endpoints
    path(
        'partials/calendar-grid/',
        views.CalendarGridPartial.as_view(),
        name='partial_calendar_grid',
    ),
]
