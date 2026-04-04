"""
ASGI config for ShiftSync project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""
import os

from django.core.asgi import get_asgi_application


# Allow environment variable to override, with dev as fallback
# On Heroku, DJANGO_SETTINGS_MODULE will be set to 'config.settings.prod'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

application = get_asgi_application()
