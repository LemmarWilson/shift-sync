"""
Forms for the scheduling app.

This module contains Django forms and model forms for handling user input
in scheduling operations, including shift creation and editing.
"""

from datetime import date

from django import forms
from django.core.exceptions import ValidationError

from .models import DayOffRequest, Shift


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
