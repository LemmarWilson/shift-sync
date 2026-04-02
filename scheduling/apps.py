"""Application configuration for the scheduling app."""

from django.apps import AppConfig


class SchedulingConfig(AppConfig):
    """Configuration class for the scheduling application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'scheduling'
    verbose_name = 'Employee Scheduling'

    def ready(self):
        """
        Perform initialization tasks when the app is ready.

        This method is called once Django has finished loading all apps.
        Use this for signal registration or other startup tasks.
        """
        # Import signals here to avoid circular imports
        # from . import signals  # noqa: F401
        pass
