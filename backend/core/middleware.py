"""Response headers Django does not set on its own.

Django's SecurityMiddleware covers HSTS, nosniff and the referrer policy.
These two it leaves alone, and both matter for an API that is reached from a
browser.
"""

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

# The API answers JSON and nothing else: no scripts, no styles, no frames, no
# embedded anything. Declaring that outright means a response that somehow
# carried markup still could not execute it.
#
# The SPA's own policy is a separate, looser one and belongs in the Nginx
# config that serves the HTML, not here.
API_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)

# The API has no use for any of these, and the browser should know it.
PERMISSIONS_POLICY = "geolocation=(), microphone=(), camera=(), payment=(), usb=()"


class SecurityHeadersMiddleware:
    """Adds the headers above to every API response."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        # The admin is server-rendered HTML with its own scripts and styles,
        # so the API's `default-src 'none'` would break it.
        if request.path.startswith("/api/"):
            response.setdefault("Content-Security-Policy", API_CONTENT_SECURITY_POLICY)
            response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)

        return response
