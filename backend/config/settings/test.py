"""Settings for the test suite.

Inherits the development configuration and removes its two dependencies on
running infrastructure, so `pytest` needs nothing but PostgreSQL.
"""

from .dev import *  # noqa: F403

# Throttle counters and any other cached state stay in the process, so tests
# neither require Redis nor leak state into a running development instance.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "braindock-tests",
    }
}

# Tasks run inline. The reminder tests call the tick directly anyway; this
# just removes the broker from the picture entirely.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# Hashing dominates the runtime of any test that creates a user.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
