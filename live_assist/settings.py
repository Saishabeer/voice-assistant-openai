import os
from pathlib import Path
# at top (with other imports)
from celery.schedules import crontab

# ensure timezone is set for local-time schedules
CELERY_TIMEZONE = os.environ.get("CELERY_TIMEZONE", "Asia/Kolkata")  # set to your TZ
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = lambda *_, **__: None

# Load environment variables from a .env file in the project root.
# This is used for sensitive data like SECRET_KEY and OPENAI_API_KEY.
load_dotenv()

# Define the project's base directory (C:/Users/saish/Desktop/voice assist).
BASE_DIR = Path(__file__).resolve().parent.parent

# A secret key for cryptographic signing, loaded from the .env file.
# The default is for development only and should not be used in production.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret")

# DEBUG mode should be False in a production environment.
DEBUG = True

# Defines the host/domain names that this Django site can serve.
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Application definition: lists all Django apps that are activated in this project.
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",

    "voice",  # Our custom application for the voice assistant.
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# The root URL configuration file for the project.
ROOT_URLCONF = "live_assist.urls"

# Configuration for Django's template engine.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # A single global directory for templates.
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# WSGI entry-point for web servers.
WSGI_APPLICATION = "live_assist.wsgi.application"

# ASGI entry-point for asynchronous web servers (used by Django Channels for WebSockets, if enabled).
ASGI_APPLICATION = "live_assist.asgi.application"

# Database configuration: PostgreSQL (credentials loaded from .env)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "voice_db"),
        "USER": os.environ.get("POSTGRES_USER", "voice_user"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}
# Auth redirects (ensures logout sends you back to home and login returns to home)
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "index"
LOGOUT_REDIRECT_URL = "index"

# Internationalization settings.
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
# Default primary key field type for new models.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom application setting: Load the OpenAI API key from the .env file.
# This key is used for server-side API calls, like creating sessions and summarizing conversations.
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
# These flags are read in `voice/views.py` save_conversation()
VOICE_SYNC_FINALIZE = True
VOICE_USE_CELERY_FINALIZE = True

# Optional Celery configuration (pulled from env). If you don't have Redis, you can set
# When Redis is available, set broker/backends accordingly.
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"))
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"))
CELERY_TIMEZONE = os.environ.get("CELERY_TIMEZONE", "UTC")
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "").lower() in ("1", "true", "yes")
CELERY_TASK_EAGER_PROPAGATES = os.environ.get("CELERY_TASK_EAGER_PROPAGATES", "").lower() in ("1", "true", "yes")

# Celery Beat: run admin stats email every 30 minutes
CELERY_BEAT_SCHEDULE = {
    "voice_admin_stats_every_30m": {
        "task": "voice.tasks_reports.send_admin_stats",
        #"schedule": 1800.0,  # seconds (30 minutes)
        #"schedule": 1800.0,  # seconds (30 minutes)
#"schedule": crontab(minute=0, hour=0),  # uses CELERY_TIMEZONE
        "schedule": 5.0,  # seconds (30 minutes)
    }
}

# Email configuration (set via environment for production)
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1").lower() in ("1", "true", "yes")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@example.com")

# Optional: derive ADMINS from comma-separated ADMIN_EMAILS env var if provided
_ADMIN_EMAILS = os.environ.get("ADMIN_EMAILS", "").strip()
if _ADMIN_EMAILS:
    ADMINS = [(e.strip(), e.strip()) for e in _ADMIN_EMAILS.split(",") if e.strip()]