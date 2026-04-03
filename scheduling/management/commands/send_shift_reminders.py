"""
Management command to send shift reminder emails.

Sends reminder emails to all employees who have published shifts
scheduled for tomorrow. Designed to be run daily via cron or scheduler.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from scheduling.models import Shift
from scheduling.services import EmailService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Send shift reminders to employees for their shifts tomorrow.

    This command queries all published shifts scheduled for tomorrow
    and sends a reminder email to each employee. It handles edge cases
    such as employees without email addresses and provides detailed
    logging and console output.

    Usage:
        python manage.py send_shift_reminders

    Typical scheduling (crontab):
        0 18 * * * cd /path/to/project && python manage.py send_shift_reminders
    """

    help = 'Send shift reminders to employees for their shifts tomorrow'

    def handle(self, *args, **options):
        """
        Execute the command to send shift reminders.

        Queries all published shifts for tomorrow and sends reminder
        emails to each employee. Outputs a summary of results.
        """
        tomorrow = timezone.now().date() + timedelta(days=1)

        self.stdout.write(
            f"Looking for published shifts on {tomorrow.strftime('%A, %B %d, %Y')}..."
        )

        # Query all published shifts for tomorrow
        shifts = Shift.objects.filter(
            date=tomorrow,
            published=True,
        ).select_related('employee', 'department')

        total_shifts = shifts.count()

        if total_shifts == 0:
            self.stdout.write(
                self.style.WARNING('No published shifts found for tomorrow.')
            )
            logger.info(f"No shifts to remind for {tomorrow}")
            return

        self.stdout.write(f"Found {total_shifts} shift(s) for tomorrow.")

        sent_count = 0
        skipped_count = 0
        failed_count = 0

        for shift in shifts:
            # Skip employees without email addresses
            if not shift.employee.email:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipped: {shift.employee.get_full_name() or shift.employee.username} "
                        f"(no email address)"
                    )
                )
                logger.warning(
                    f"Skipped shift reminder for {shift.employee} - no email address"
                )
                skipped_count += 1
                continue

            # Send the reminder email
            success = EmailService.send_shift_reminder(shift)

            if success:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Sent: {shift.employee.email} - "
                        f"{shift.start_time.strftime('%I:%M %p')} to "
                        f"{shift.end_time.strftime('%I:%M %p')}"
                    )
                )
                logger.info(
                    f"Sent shift reminder to {shift.employee.email} for shift on {tomorrow}"
                )
                sent_count += 1
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"  Failed: {shift.employee.email}"
                    )
                )
                failed_count += 1

        # Output summary
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {sent_count} reminder(s) for {total_shifts} shift(s)"
            )
        )

        if skipped_count > 0:
            self.stdout.write(
                self.style.WARNING(f"Skipped {skipped_count} (no email)")
            )

        if failed_count > 0:
            self.stdout.write(
                self.style.ERROR(f"Failed {failed_count}")
            )

        logger.info(
            f"Shift reminders complete: {sent_count} sent, "
            f"{skipped_count} skipped, {failed_count} failed"
        )
