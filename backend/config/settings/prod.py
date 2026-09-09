"""Production settings.

`manage.py check --deploy` passes on this module, but that check only looks at
a fixed list of flags. The comments below mark the decisions it cannot see.
"""

from .base import *  # noqa: F403
from .base import REST_FRAMEWORK, env

DEBUG = False

# No default. A missing value has to stop the process, because the fallback
# for ALLOWED_HOSTS would be to trust whatever Host header arrives.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Nginx terminates TLS and forwards the original scheme.
#
# This header is only trustworthy because Nginx sets it on every proxied
# request rather than passing a client-supplied one through. If that ever
# stops being true, a request could claim to be HTTPS and defeat the redirect
# and the secure-cookie flags at once.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# Two weeks, refreshed on use: long enough for a personal tool, short enough
# that an abandoned session does not stay valid indefinitely.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
# Deliberately readable by scripts. The SPA has to copy this value into the
# X-CSRFToken header, which is the entire double-submit mechanism; making it
# HttpOnly would break every write.
CSRF_COOKIE_HTTPONLY = False

SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# Nothing here is meant to be embedded anywhere.
X_FRAME_OPTIONS = "DENY"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Behind Nginx, every request reaches Gunicorn from the same container
# address, so REMOTE_ADDR identifies the proxy rather than the caller. DRF
# falls back to X-Forwarded-For to tell clients apart for rate limiting, and
# without this setting it would trust the whole header -- including anything
# a client put there itself, which would give every request its own
# login-throttle bucket. Setting the proxy count makes DRF read only the
# entry the trusted proxy appended.
#
# It must stay in step with deploy/nginx: exactly one proxy, and that proxy
# overwrites X-Forwarded-For rather than appending to it.
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": 1}

# The admin is the one path that can change anything about any account. Moving
# it off the default address does not make it secure, but it does take it out
# of reach of the scanners that try /admin/ on every host they find.
ADMIN_URL_PATH = env("DJANGO_ADMIN_URL_PATH", default="admin/")

# The SPA is served from the same origin by Nginx, so no cross-origin access
# is needed in production.
CORS_ALLOWED_ORIGINS = []
CORS_ALLOW_CREDENTIALS = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
