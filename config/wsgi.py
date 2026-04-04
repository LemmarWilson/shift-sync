"""
WSGI config for ShiftSync project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""
import os

from django.core.wsgi import get_wsgi_application


# Allow environment variable to override, with dev as fallback
# On Heroku, DJANGO_SETTINGS_MODULE will be set to 'config.settings.prod'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

application = get_wsgi_application()
