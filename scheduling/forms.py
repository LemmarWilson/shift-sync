"""
Forms for the scheduling app.

This module contains Django forms and model forms for handling user input
in scheduling operations, including shift creation, editing, and user profile
management.
"""

from datetime import date

from django import forms
from django.core.exceptions import ValidationError

from .models import DayOffRequest, Shift, TimeEntry, User


class ShiftForm(forms.ModelForm):
    """
    ModelForm for creating and editing Shift instances.

    Provides validation to ensure:
    - End time is after start time
    - No overlapping shifts exist for the same employee on the same date

    Attributes:
        All fields use Tailwind 'form-input' class for consistent styling.
    """

    class Meta:
        model = Shift
        fields = ['employee', 'department', 'date', 'start_time', 'end_time', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-input'}),
            'department': forms.Select(attrs={'class': 'form-input'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }

    def clean(self):
        """
        Validate the shift data.

        Ensures:
        1. End time is after start time
        2. No overlapping shifts exist for the same employee on the same date

        Returns:
            The cleaned data dictionary.

        Raises:
            ValidationError: If validation fails.
        """
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        employee = cleaned_data.get('employee')
        date = cleaned_data.get('date')

        # Validate end_time > start_time
        if start_time and end_time:
            if end_time <= start_time:
                raise ValidationError(
                    'End time must be after start time.'
                )

        # Check for overlapping shifts for the same employee on the same date
        if employee and date and start_time and end_time:
            overlapping_shifts = Shift.objects.filter(
                employee=employee,
                date=date,
                start_time__lt=end_time,
                end_time__gt=start_time,
            )

            # Exclude current instance when updating
            if self.instance.pk:
                overlapping_shifts = overlapping_shifts.exclude(pk=self.instance.pk)

            if overlapping_shifts.exists():
                raise ValidationError(
                    'This shift overlaps with an existing shift for this employee.'
                )

        return cleaned_data


class DayOffRequestForm(forms.ModelForm):
    """Form for employees to submit day-off requests."""

    class Meta:
        model = DayOffRequest
        fields = ['start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500'
            }),
            'reason': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
                'placeholder': 'Reason for time off...'
            }),
        }

    def clean(self):
        """
        Validate the day-off request data.

        Ensures:
        1. End date is on or after start date
        2. Start date is not in the past

        Returns:
            The cleaned data dictionary.

        Raises:
            ValidationError: If validation fails.
        """
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')

        if start and end and end < start:
            raise ValidationError('End date must be on or after start date.')

        if start and start < date.today():
            raise ValidationError('Cannot request time off for past dates.')

        return cleaned_data


class UserProfileForm(forms.ModelForm):
    """
    ModelForm for editing user profile information.

    Allows users to update their username, email, phone, first name,
    and last name. All fields use consistent Tailwind styling.
    """

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Username',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'Email address',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'First name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Last name',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Phone number',
            }),
        }

    def clean_email(self):
        """
        Validate that the email is unique among users.

        Excludes the current user from the uniqueness check to allow
        users to keep their existing email.

        Returns:
            The cleaned email value.

        Raises:
            ValidationError: If the email is already in use by another user.
        """
        email = self.cleaned_data.get('email')
        if email:
            # Check if another user already has this email
            existing = User.objects.filter(email=email).exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('This email is already in use.')
        return email

    def clean_username(self):
        """
        Validate that the username is unique among users.

        Excludes the current user from the uniqueness check to allow
        users to keep their existing username.

        Returns:
            The cleaned username value.

        Raises:
            ValidationError: If the username is already in use by another user.
        """
        username = self.cleaned_data.get('username')
        if username:
            # Check if another user already has this username
            existing = User.objects.filter(username=username).exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('This username is already taken.')
        return username


class PasswordChangeForm(forms.Form):
    """
    Form for changing user password.

    Requires the current password for verification and validates
    that new passwords match and meet minimum length requirements.
    """

    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Current password',
        }),
        label='Current Password',
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'New password',
        }),
        label='New Password',
        min_length=8,
        help_text='Password must be at least 8 characters.',
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirm new password',
        }),
        label='Confirm New Password',
    )

    def __init__(self, user, *args, **kwargs):
        """
        Initialize the form with the user whose password will be changed.

        Args:
            user: The User instance whose password is being changed.
            *args: Variable positional arguments passed to Form.__init__.
            **kwargs: Variable keyword arguments passed to Form.__init__.
        """
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        """
        Validate that the old password is correct.

        Returns:
            The cleaned old password value.

        Raises:
            ValidationError: If the old password is incorrect.
        """
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise ValidationError('Current password is incorrect.')
        return old_password

    def clean(self):
        """
        Validate that the new passwords match.

        Returns:
            The cleaned data dictionary.

        Raises:
            ValidationError: If the new passwords do not match.
        """
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError('New passwords do not match.')

        return cleaned_data


class TimeEntryForm(forms.ModelForm):
    """Form for managers to edit time entries."""

    clock_in = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white',
            }
        )
    )
    clock_out = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={
                'type': 'datetime-local',
                'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white',
            }
        )
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                'rows': 2,
                'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 dark:bg-gray-700 dark:text-white',
                'placeholder': 'Adjustment notes (optional)...',
            }
        )
    )

    class Meta:
        model = TimeEntry
        fields = ['clock_in', 'clock_out', 'notes']
