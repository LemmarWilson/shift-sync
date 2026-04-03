"""
Base Django settings for ShiftSync project.

This module contains settings shared across all environments.
Environment-specific settings should be placed in dev.py or prod.py.
"""
from pathlib import Path

from decouple import config, Csv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# =============================================================================
# SECURITY SETTINGS
# =============================================================================

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())


# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = []

LOCAL_APPS = [
    'scheduling',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# =============================================================================
# URL CONFIGURATION
# =============================================================================

ROOT_URLCONF = 'config.urls'


# =============================================================================
# TEMPLATES
# =============================================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# =============================================================================
# WSGI APPLICATION
# =============================================================================

WSGI_APPLICATION = 'config.wsgi.application'


# =============================================================================
# AUTHENTICATION
# =============================================================================

AUTH_USER_MODEL = 'scheduling.User'

# Authentication backends - email first, then username fallback
AUTHENTICATION_BACKENDS = [
    'scheduling.backends.EmailAuthenticationBackend',  # Authenticate by email
    'django.contrib.auth.backends.ModelBackend',       # Fallback to username
]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'scheduling:calendar'
LOGOUT_REDIRECT_URL = 'login'


# =============================================================================
# PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        },
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = 'en-us'

TIME_ZONE = config('TIME_ZONE', default='America/New_York')

USE_I18N = True

USE_TZ = True


# =============================================================================
# STATIC FILES (CSS, JavaScript, Images)
# =============================================================================

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'


# =============================================================================
# MEDIA FILES (User uploads)
# =============================================================================

MEDIA_URL = 'media/'

MEDIA_ROOT = BASE_DIR / 'mediafiles'


# =============================================================================
# DEFAULT PRIMARY KEY FIELD TYPE
# =============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# =============================================================================
# EMAIL CONFIGURATION
# =============================================================================

DEFAULT_FROM_EMAIL = config(
    'DEFAULT_FROM_EMAIL',
    default='ShiftSync <noreply@shiftsync.example.com>'
)

EMAIL_SUBJECT_PREFIX = '[ShiftSync] '
