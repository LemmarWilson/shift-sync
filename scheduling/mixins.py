"""
Mixins for class-based views with role-based access control.

This module provides reusable mixins for Django class-based views that
enforce authentication and role requirements for the ShiftSync application.
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class ManagerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin that requires the user to be authenticated and have manager role.

    Combines LoginRequiredMixin and UserPassesTestMixin to provide a clean
    way to restrict class-based views to managers only. Unauthenticated users
    are redirected to the login page; authenticated non-managers receive a
    403 Forbidden response.

    Attributes:
        raise_exception: Inherited from UserPassesTestMixin, controls whether
            to raise PermissionDenied or redirect. We override handle_no_permission
            to provide custom behavior.

    Usage:
        class ShiftCreateView(ManagerRequiredMixin, CreateView):
            model = Shift
            # Only managers can create shifts
            ...

        class DepartmentUpdateView(ManagerRequiredMixin, UpdateView):
            model = Department
            # Only managers can update departments
            ...
    """

    def test_func(self) -> bool:
        """
        Test if the current user has manager role.

        Returns:
            True if the user is a manager, False otherwise.
        """
        return self.request.user.is_manager

    def handle_no_permission(self):
        """
        Handle the case when the user fails the permission test.

        For authenticated users who are not managers, raises PermissionDenied
        with a clear error message. For unauthenticated users, falls back to
        the default LoginRequiredMixin behavior (redirect to login).

        Raises:
            PermissionDenied: If the user is authenticated but not a manager.
        """
        if self.request.user.is_authenticated:
            raise PermissionDenied("You must be a manager to access this page.")
        return super().handle_no_permission()


class EmployeeRequiredMixin(LoginRequiredMixin):
    """
    Mixin that requires the user to be authenticated (any role).

    This is functionally equivalent to Django's LoginRequiredMixin,
    but provides explicit semantic meaning in the codebase that this view
    is intended for authenticated employees (which includes managers).

    Using this mixin instead of LoginRequiredMixin directly makes the
    code more self-documenting and consistent with the role-based access
    control pattern used throughout the application.

    Usage:
        class MyShiftsView(EmployeeRequiredMixin, ListView):
            model = Shift
            # Any authenticated user can view their shifts
            ...

        class ProfileUpdateView(EmployeeRequiredMixin, UpdateView):
            model = User
            # Any authenticated user can update their profile
            ...
    """

    pass
