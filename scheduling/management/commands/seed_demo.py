"""
Management command to seed the database with demo data.

This command creates a complete set of demo data for testing and demonstrations,
including users, departments, shifts, day-off requests, and notifications.
All demo data uses @demo.com email addresses for easy identification and cleanup.

Usage:
    python manage.py seed_demo          # Create demo data
    python manage.py seed_demo --clear  # Clear existing demo data first
"""

import logging
import random
from datetime import date, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from scheduling.models import DayOffRequest, Department, Notification, Shift, User

logger = logging.getLogger(__name__)

# Demo data constants
DEMO_EMAIL_SUFFIX = '@demo.com'
DEMO_PASSWORD = 'demo123'

EMPLOYEE_LAST_NAMES = ['One', 'Two', 'Three', 'Four', 'Five']

DEPARTMENT_NAMES = ['Front Desk', 'Kitchen']

SHIFT_START_TIMES = [
    time(8, 0),
    time(9, 0),
    time(10, 0),
    time(11, 0),
    time(12, 0),
    time(14, 0),
]

SHIFT_DURATIONS_HOURS = [4, 5, 6, 7, 8]

SHIFT_NOTES = [
    '',
    'Opening shift - arrive 15 mins early',
    'Closing shift - complete checklist',
    'Training session included',
    'Cover for team meeting',
    '',
]


class Command(BaseCommand):
    """Management command to seed the database with demo data for testing."""

    help = 'Seed the database with demo data for testing and demonstrations'

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing demo data before seeding',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        if options['clear']:
            self.clear_demo_data()

        self.create_demo_data()

    def clear_demo_data(self):
        """
        Delete all existing demo data.

        Removes users with @demo.com emails along with their associated
        shifts, day-off requests, and notifications. Also removes demo departments.
        """
        self.stdout.write('Clearing existing demo data...')

        with transaction.atomic():
            # Get demo users (cascade will handle shifts, day-off requests, notifications)
            demo_users = User.objects.filter(email__endswith=DEMO_EMAIL_SUFFIX)
            user_count = demo_users.count()

            # Count related objects before deletion for reporting
            shift_count = Shift.objects.filter(employee__in=demo_users).count()
            dayoff_count = DayOffRequest.objects.filter(employee__in=demo_users).count()
            notification_count = Notification.objects.filter(recipient__in=demo_users).count()

            # Delete demo departments (must happen before users due to manager FK)
            demo_departments = Department.objects.filter(name__in=DEPARTMENT_NAMES)
            dept_count = demo_departments.count()
            demo_departments.delete()

            # Delete demo users (cascades to shifts, day-off requests, notifications)
            demo_users.delete()

        self.stdout.write(
            self.style.WARNING(
                f'Cleared: {user_count} users, {dept_count} departments, '
                f'{shift_count} shifts, {dayoff_count} day-off requests, '
                f'{notification_count} notifications'
            )
        )

    def create_demo_data(self):
        """
        Create all demo data.

        Creates manager, employees, departments, shifts, day-off requests,
        and notifications in a single transaction.
        """
        self.stdout.write('Creating demo data...')

        # Check if demo data already exists
        if User.objects.filter(email=f'manager{DEMO_EMAIL_SUFFIX}').exists():
            self.stdout.write(
                self.style.WARNING(
                    'Demo data already exists. Use --clear to reset.'
                )
            )
            return

        with transaction.atomic():
            manager = self._create_manager()
            employees = self._create_employees()
            departments = self._create_departments(manager, employees)
            shifts = self._create_shifts(manager, employees, departments)
            dayoff_requests = self._create_dayoff_requests(employees)
            notifications = self._create_notifications(manager, employees)

        self._print_summary(
            manager, employees, departments, shifts, dayoff_requests, notifications
        )

    def _create_manager(self) -> User:
        """Create the demo manager user."""
        manager = User.objects.create_user(
            username='demo_manager',
            email=f'manager{DEMO_EMAIL_SUFFIX}',
            password=DEMO_PASSWORD,
            first_name='Demo',
            last_name='Manager',
            role=User.Role.MANAGER,
        )
        self.stdout.write(f'  Created manager: {manager.email}')
        return manager

    def _create_employees(self) -> list[User]:
        """Create demo employee users."""
        employees = []
        for i, last_name in enumerate(EMPLOYEE_LAST_NAMES, start=1):
            employee = User.objects.create_user(
                username=f'demo_employee{i}',
                email=f'employee{i}{DEMO_EMAIL_SUFFIX}',
                password=DEMO_PASSWORD,
                first_name='Employee',
                last_name=last_name,
                role=User.Role.EMPLOYEE,
            )
            employees.append(employee)
            self.stdout.write(f'  Created employee: {employee.email}')
        return employees

    def _create_departments(
        self, manager: User, employees: list[User]
    ) -> list[Department]:
        """Create demo departments and assign employees."""
        departments = []

        for i, name in enumerate(DEPARTMENT_NAMES):
            department = Department.objects.create(
                name=name,
                manager=manager,
            )
            departments.append(department)
            self.stdout.write(f'  Created department: {name}')

        # Split employees between departments
        for i, employee in enumerate(employees):
            department = departments[i % len(departments)]
            employee.department = department
            employee.save()
            self.stdout.write(
                f'    Assigned {employee.get_full_name()} to {department.name}'
            )

        return departments

    def _create_shifts(
        self,
        manager: User,
        employees: list[User],
        departments: list[Department],
    ) -> list[Shift]:
        """
        Create two weeks of sample shifts for all employees.

        Each employee gets 4-5 shifts per week with varying times,
        publication status, and optional notes.
        """
        shifts = []
        today = timezone.localdate()

        # Get Monday of current week
        days_since_monday = today.weekday()
        current_week_monday = today - timedelta(days=days_since_monday)

        # Generate 14 days (current week + next week)
        all_dates = [current_week_monday + timedelta(days=i) for i in range(14)]

        for employee in employees:
            # Determine employee's department
            department = employee.department

            # Select 8-10 random days for shifts across the 2 weeks
            num_shifts = random.randint(8, 10)
            shift_dates = random.sample(all_dates, min(num_shifts, len(all_dates)))

            for shift_date in shift_dates:
                start_time = random.choice(SHIFT_START_TIMES)
                duration = random.choice(SHIFT_DURATIONS_HOURS)

                # Calculate end time
                end_hour = start_time.hour + duration
                end_minute = start_time.minute

                # Handle overnight shifts (cap at 23:00)
                if end_hour >= 24:
                    end_hour = 23
                    end_minute = 0

                end_time = time(end_hour, end_minute)

                # Mix of published and unpublished (70% published)
                published = random.random() < 0.7

                # Random notes (50% have notes)
                notes = random.choice(SHIFT_NOTES)

                try:
                    shift = Shift.objects.create(
                        employee=employee,
                        department=department,
                        date=shift_date,
                        start_time=start_time,
                        end_time=end_time,
                        published=published,
                        created_by=manager,
                        notes=notes,
                    )
                    shifts.append(shift)
                except Exception as e:
                    # Skip duplicate shifts (same employee, date, start_time)
                    logger.debug(f'Skipped duplicate shift: {e}')

        self.stdout.write(f'  Created {len(shifts)} shifts')
        return shifts

    def _create_dayoff_requests(self, employees: list[User]) -> list[DayOffRequest]:
        """
        Create pending day-off requests for demo purposes.

        Creates two pending requests from different employees with
        dates in the current and next week.
        """
        dayoff_requests = []
        today = timezone.localdate()

        # Get next week dates
        days_until_next_monday = 7 - today.weekday()
        next_monday = today + timedelta(days=days_until_next_monday)

        # Request 1: Employee One - next week (3 days)
        if len(employees) >= 1:
            request1 = DayOffRequest.objects.create(
                employee=employees[0],  # Employee One
                start_date=next_monday,
                end_date=next_monday + timedelta(days=2),
                reason='Personal appointment',
                status=DayOffRequest.Status.PENDING,
            )
            dayoff_requests.append(request1)
            self.stdout.write(
                f'  Created day-off request: {employees[0].get_full_name()} '
                f'({request1.start_date} to {request1.end_date})'
            )

        # Request 2: Employee Three - spans current and next week
        if len(employees) >= 3:
            # Start on Friday of current week, end Tuesday of next week
            days_until_friday = 4 - today.weekday()
            if days_until_friday < 0:
                days_until_friday += 7
            friday = today + timedelta(days=days_until_friday)

            request2 = DayOffRequest.objects.create(
                employee=employees[2],  # Employee Three
                start_date=friday,
                end_date=friday + timedelta(days=4),
                reason='Family vacation',
                status=DayOffRequest.Status.PENDING,
            )
            dayoff_requests.append(request2)
            self.stdout.write(
                f'  Created day-off request: {employees[2].get_full_name()} '
                f'({request2.start_date} to {request2.end_date})'
            )

        return dayoff_requests

    def _create_notifications(
        self, manager: User, employees: list[User]
    ) -> list[Notification]:
        """
        Create sample notifications for demo purposes.

        Creates notifications for the manager about pending day-off requests
        and for employees about shift assignments.
        """
        notifications = []

        # Manager notifications (about day-off requests)
        manager_messages = [
            ('New day-off request from Employee One', '/dayoff/', False),
            ('New day-off request from Employee Three', '/dayoff/', False),
            ('Weekly schedule reminder: Review unpublished shifts', '/shifts/', True),
        ]

        for message, link, read in manager_messages:
            notification = Notification.objects.create(
                recipient=manager,
                message=message,
                link=link,
                read=read,
            )
            notifications.append(notification)

        self.stdout.write(f'  Created {len(manager_messages)} manager notifications')

        # Employee notifications (about shift assignments)
        employee_notification_count = 0
        for i, employee in enumerate(employees):
            # 2 notifications per employee
            employee_messages = [
                (
                    f'You have been assigned a new shift',
                    '/calendar/',
                    i % 2 == 0,  # Alternate read/unread
                ),
                (
                    f'Your schedule for next week is ready',
                    '/calendar/',
                    True,  # Read
                ),
            ]

            for message, link, read in employee_messages:
                notification = Notification.objects.create(
                    recipient=employee,
                    message=message,
                    link=link,
                    read=read,
                )
                notifications.append(notification)
                employee_notification_count += 1

        self.stdout.write(
            f'  Created {employee_notification_count} employee notifications'
        )

        return notifications

    def _print_summary(
        self,
        manager: User,
        employees: list[User],
        departments: list[Department],
        shifts: list[Shift],
        dayoff_requests: list[DayOffRequest],
        notifications: list[Notification],
    ):
        """Print a summary of all created demo data."""
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Demo data created successfully!'))
        self.stdout.write('')
        self.stdout.write('Summary:')
        self.stdout.write(f'  Users: {1 + len(employees)} (1 manager, {len(employees)} employees)')
        self.stdout.write(f'  Departments: {len(departments)}')
        self.stdout.write(f'  Shifts: {len(shifts)}')
        self.stdout.write(f'  Day-off requests: {len(dayoff_requests)}')
        self.stdout.write(f'  Notifications: {len(notifications)}')
        self.stdout.write('')
        self.stdout.write('Login credentials:')
        self.stdout.write(f'  Manager: manager{DEMO_EMAIL_SUFFIX} / {DEMO_PASSWORD}')
        self.stdout.write(f'  Employees: employee1{DEMO_EMAIL_SUFFIX} to employee5{DEMO_EMAIL_SUFFIX} / {DEMO_PASSWORD}')
