"""Settings shared by every environment.

Environment-specific modules (dev, prod) import everything from here and only
override what genuinely differs. Nothing in this module may depend on DEBUG.
"""

from pathlib import Path

import environ
from celery.schedules import crontab

# BASE_DIR points at the `backend/` directory: this file is
# backend/config/settings/base.py, so three parents up.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "django_filters",
]

LOCAL_APPS = [
    "core",
    "apps.users",
    "apps.ideas",
    "apps.reminders",
    "apps.notifications",
    "apps.telegrambot",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------

# Must be set before the very first migrate. Swapping it later requires
# dropping the database.
AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# Internationalization
# --------------------------------------------------------------------------

LANGUAGE_CODE = "fa"
USE_I18N = True

# Everything is stored in UTC. Conversion to the Jalali calendar happens only
# at the presentation layer (UI and Telegram messages), never in the database.
TIME_ZONE = "UTC"
USE_TZ = True

# The single timezone all user-facing scheduling is expressed in. The reminder
# engine resolves "every day at 09:00" against this zone before converting the
# result back to UTC for storage.
USER_TIME_ZONE = "Asia/Tehran"

# --------------------------------------------------------------------------
# Static and media files
# --------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Attachments are private, so MEDIA_ROOT is never exposed by the web server.
# Every download goes through a view that checks ownership and then hands the
# file back to Nginx through this internal location, which is declared
# `internal;` in the server config and so cannot be requested from outside.
MEDIA_INTERNAL_URL = "/internal-media/"

# --------------------------------------------------------------------------
# Attachments
# --------------------------------------------------------------------------

MAX_IMAGE_UPLOAD_BYTES = env.int("MAX_IMAGE_UPLOAD_BYTES", default=10 * 1024 * 1024)
MAX_AUDIO_UPLOAD_BYTES = env.int("MAX_AUDIO_UPLOAD_BYTES", default=25 * 1024 * 1024)

# Bounding box for the grid preview on the note page.
ATTACHMENT_THUMBNAIL_SIZE = (800, 600)

# Uploads above this size are streamed to a temporary file instead of being
# held in memory.
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

# --------------------------------------------------------------------------
# Django REST Framework
# --------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    # Throttles are opt-in per view rather than global; the login endpoint is
    # the one that needs a cap in this phase.
    "DEFAULT_THROTTLE_RATES": {
        "login": env("LOGIN_THROTTLE_RATE", default="10/min"),
        "telegram_webhook": env("WEBHOOK_THROTTLE_RATE", default="120/min"),
    },
}

# --------------------------------------------------------------------------
# Celery
# --------------------------------------------------------------------------

REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# Celery works in UTC like everything else; the Jalali calendar and the
# Tehran clock exist only at the presentation layer.
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True

# A task that outlives its next scheduled run would let two ticks overlap.
CELERY_TASK_TIME_LIMIT = 55
CELERY_TASK_SOFT_TIME_LIMIT = 45

# The project's entire schedule. Reminders are not queued individually -- one
# tick reads the rows that have come due. See apps.reminders.tasks for why.
CELERY_BEAT_SCHEDULE = {
    "dispatch-due-reminders": {
        "task": "reminders.dispatch_due",
        "schedule": 60.0,
        # A tick that could not run on time is worthless a minute later; the
        # next one will pick up the same rows anyway.
        "options": {"expires": 55},
    },
    # Once a day. "You have not touched this in two weeks" does not become
    # truer at a finer resolution, and the job is idempotent anyway: an idea
    # already reported is not reported again until it is edited.
    #
    # The schedule is in UTC like everything else. 05:30 UTC is 09:00 in
    # Tehran, which is where the hour is meant to land.
    "send-stale-digests": {
        "task": "notifications.send_stale_digests",
        "schedule": crontab(hour=5, minute=30),
    },
}

# Throttle counters and Celery share one Redis instance. In development this
# falls back to local memory so the app runs without Redis at all.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# --------------------------------------------------------------------------
# Telegram
# --------------------------------------------------------------------------

# The bot itself lands in phase 6; the username is needed before that so
# the settings page can render a working t.me link.
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME", default="BrainDockBot")
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")

# Handed to setWebhook and echoed back by Telegram in a header. It is the
# only thing standing between the webhook and the open internet, so an unset
# value makes the endpoint refuse everything rather than accept everything.
TELEGRAM_WEBHOOK_SECRET = env("TELEGRAM_WEBHOOK_SECRET", default="")

# Where the bot's links point. Also used by the stale digest in phase 7.
SITE_URL = env("SITE_URL", default="http://localhost:5173")

# --------------------------------------------------------------------------
# Application metadata
# --------------------------------------------------------------------------

APP_VERSION = "0.1.0"
