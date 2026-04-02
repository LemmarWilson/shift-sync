"""
Development settings for ShiftSync project.

These settings are intended for local development only.
Do NOT use in production.
"""
from .base import *  # noqa: F401, F403


# =============================================================================
# DEBUG SETTINGS
# =============================================================================

DEBUG = True


# =============================================================================
# DATABASE
# =============================================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
    }
}


# =============================================================================
# EMAIL BACKEND
# =============================================================================

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# =============================================================================
# DEVELOPMENT-SPECIFIC APPS
# =============================================================================

# Add any development-only apps here
# INSTALLED_APPS += ['debug_toolbar']


# =============================================================================
# DEVELOPMENT-SPECIFIC MIDDLEWARE
# =============================================================================

# Add any development-only middleware here
# MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']


# =============================================================================
# DEBUG TOOLBAR SETTINGS (if enabled)
# =============================================================================

INTERNAL_IPS = [
    '127.0.0.1',
]


# =============================================================================
# LOGGING
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'scheduling': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
