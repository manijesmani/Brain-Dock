"""Local development settings."""

from .base import *  # noqa: F403
from .base import env

DEBUG = True

# Overridable so a tunnel's hostname can be added when testing the Telegram
# webhook, which Telegram will only deliver to a public HTTPS address. The
# default is the local set, so nothing has to be configured to run normally.
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "[::1]"],
)

# The Vite dev server runs on its own origin and talks to Django through a
# proxy, but direct cross-origin calls are allowed here so the frontend can be
# pointed at the API without the proxy while debugging.
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173"],
)
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
