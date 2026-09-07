"""A single, predictable error shape for the whole API.

DRF returns validation errors as a bare field-to-messages mapping but other
errors as `{"detail": ...}`. The frontend would need two code paths for that,
so every error is normalised here into:

    {"detail": str, "code": str, "errors": dict | None}

`errors` is populated only for field validation failures.
"""

from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

# Fallback messages, in Persian, for the cases DRF words in English.
DEFAULT_MESSAGES = {
    400: "درخواست نامعتبر است.",
    401: "برای این کار باید وارد شوی.",
    403: "به این بخش دسترسی نداری.",
    404: "چیزی که دنبالش بودی پیدا نشد.",
    405: "این روش درخواست پشتیبانی نمی‌شود.",
    429: "تعداد درخواست‌ها زیاد بود. کمی بعد دوباره تلاش کن.",
    500: "خطای غیرمنتظره‌ای رخ داد.",
}


def _flatten_detail(detail: Any) -> str:
    """Pull a single human-readable sentence out of a nested DRF detail."""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        return _flatten_detail(detail[0])
    if isinstance(detail, dict) and detail:
        return _flatten_detail(next(iter(detail.values())))
    return DEFAULT_MESSAGES[400]


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    # Translate the Django-level equivalents so they are handled here too
    # rather than escaping as unhandled 500s.
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        # Not a DRF exception: let Django's own handler produce the 500 so the
        # traceback still reaches the logs.
        return None

    status_code = response.status_code
    errors: dict[str, Any] | None = None
    detail = response.data

    if isinstance(exc, exceptions.ValidationError) and isinstance(detail, dict):
        errors = detail
        message = _flatten_detail(detail)
    else:
        if isinstance(detail, dict) and "detail" in detail:
            message = _flatten_detail(detail["detail"])
        else:
            message = _flatten_detail(detail)

    if not message or message == "":
        message = DEFAULT_MESSAGES.get(status_code, DEFAULT_MESSAGES[400])

    code = getattr(exc, "default_code", "error")
    if isinstance(detail, dict) and isinstance(detail.get("detail"), exceptions.ErrorDetail):
        code = detail["detail"].code

    response.data = {"detail": message, "code": code, "errors": errors}
    return response
