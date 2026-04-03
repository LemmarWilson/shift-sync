"""
Custom decorators for role-based access control.

This module provides function-based view decorators that enforce
authentication and role requirements for the ShiftSync application.
"""

from functools import wraps
from typing import Callable

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect


def manager_required(view_func: Callable) -> Callable:
    """
    Decorator that requires the user to be authenticated and have manager role.

    Checks authentication first, redirecting unauthenticated users to the login
    page. For authenticated users without manager role, raises PermissionDenied.

    Args:
        view_func: The view function to wrap.

    Returns:
        The wrapped view function with manager role enforcement.

    Raises:
        PermissionDenied: If the authenticated user is not a manager.

    Usage:
        @manager_required
        def my_view(request):
            # Only managers can access this view
            ...

        # Can be stacked with other decorators
        @manager_required
        @require_http_methods(['GET', 'POST'])
        def another_view(request):
            ...
    """
    @wraps(view_func)
    def _wrapped_view(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_manager:
            raise PermissionDenied("You must be a manager to access this page.")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def employee_required(view_func: Callable) -> Callable:
    """
    Decorator that requires the user to be authenticated (any role).

    This is functionally equivalent to Django's login_required decorator,
    but provides explicit semantic meaning in the codebase that this view
    is intended for authenticated employees (which includes managers).

    Args:
        view_func: The view function to wrap.

    Returns:
        The wrapped view function with authentication enforcement.

    Usage:
        @employee_required
        def my_view(request):
            # Any authenticated user can access this view
            ...
    """
    return login_required(view_func)
