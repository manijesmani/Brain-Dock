"""Keeps the list of signed-in devices up to date. See apps.users.devices."""

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from apps.users import devices


class DeviceSessionMiddleware:
    """Writes down, after each request, the device it came from.

    After rather than before the view: a request that signs in has its new
    session only once the view has run.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        devices.note(request)
        return response
