from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Caps password attempts from a single address.

    Keyed on the client address rather than the submitted username, so an
    attacker cannot dodge the limit by rotating usernames.

    In development this counts against the local-memory cache; production
    moves the cache to Redis in phase 4, which is what makes the limit hold
    across Gunicorn workers.
    """

    scope = "login"
