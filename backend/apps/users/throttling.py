from rest_framework.request import Request
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle
from rest_framework.views import APIView


class LoginRateThrottle(AnonRateThrottle):
    """Caps password attempts from a single address.

    Keyed on the client address rather than the submitted username, so an
    attacker cannot dodge the limit by rotating usernames.

    In development this counts against the local-memory cache; production
    moves the cache to Redis in phase 4, which is what makes the limit hold
    across Gunicorn workers.
    """

    scope = "login"


class GuestRateThrottle(AnonRateThrottle):
    """Caps how many guest accounts one address can open.

    A browser needs one, once; this only stops a script from filling the
    user table.
    """

    scope = "guest"


class SignupRateThrottle(SimpleRateThrottle):
    """Caps sign-up attempts from a single address.

    Keyed on the address whether or not a session exists, because most
    sign-ups come from a signed-in guest, which an anonymous-only throttle
    would never count.
    """

    scope = "signup"

    def get_cache_key(self, request: Request, view: APIView) -> str:
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
