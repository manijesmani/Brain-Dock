"""A single, predictable error shape for the whole API.

DRF returns validation errors as a bare field-to-messages mapping but other
errors as `{"detail": ...}`. The frontend would need two code paths for that,
so every error is normalised here into:

    {"detail": str, "code": str, "errors": dict | None}

`errors` is populated only for field validation failures.
"""

import logging
import re
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from core.formatting import to_persian_digits

logger = logging.getLogger(__name__)

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


# Every message a person reads must be Persian. DRF ships a Persian
# catalogue, but a few of its messages are English regardless -- a malformed
# body, a failed CSRF check -- and a few others read as literal translations.
# Those are replaced here, in the one place every error passes through.
PERSIAN_LETTERS = re.compile(r"[\u0600-\u06FF]")

REQUEST_MESSAGES: dict[type[exceptions.APIException], str] = {
    exceptions.ParseError: "داده‌های ارسالی قابل خواندن نیست.",
    exceptions.NotAuthenticated: DEFAULT_MESSAGES[401],
    exceptions.AuthenticationFailed: DEFAULT_MESSAGES[401],
    exceptions.MethodNotAllowed: DEFAULT_MESSAGES[405],
    exceptions.UnsupportedMediaType: "این نوع داده پشتیبانی نمی‌شود.",
    exceptions.Throttled: DEFAULT_MESSAGES[429],
}

CSRF_MESSAGE = (
    "این صفحه مدتی باز مانده و نشستش کهنه شده. صفحه را دوباره بارگذاری کن و دوباره امتحان کن."
)

# Field messages by their DRF code. The catalogue's own wording for a
# related record that does not exist names the database key and the word
# "Object"; the length and range ones are reworded with Persian digits.
FIELD_MESSAGES = {
    "does_not_exist": "مورد انتخاب‌شده پیدا نشد.",
    "incorrect_type": "مورد انتخاب‌شده معتبر نیست.",
}
LIMIT_MESSAGES = {
    "max_length": "این مقدار نباید بیشتر از {} حرف باشد.",
    "min_length": "این مقدار نباید کمتر از {} حرف باشد.",
    "max_value": "این مقدار باید حداکثر {} باشد.",
    "min_value": "این مقدار باید دست‌کم {} باشد.",
}
FIELD_FALLBACK = "مقدار واردشده معتبر نیست."


def _field_message(item: Any) -> str:
    text = str(item)
    code = getattr(item, "code", None)

    if code in FIELD_MESSAGES:
        return FIELD_MESSAGES[code]
    if code in LIMIT_MESSAGES and (number := re.search(r"\d+", text)):
        return LIMIT_MESSAGES[code].format(to_persian_digits(number.group()))
    if not PERSIAN_LETTERS.search(text):
        return FIELD_FALLBACK
    return text


def _translate(detail: Any) -> Any:
    """Rewrites every message in a (possibly nested) validation detail."""
    if isinstance(detail, dict):
        return {key: _translate(value) for key, value in detail.items()}
    if isinstance(detail, list):
        return [_translate(value) for value in detail]
    return _field_message(detail)


def _request_message(exc: exceptions.APIException, message: str, status_code: int) -> str:
    for kind, replacement in REQUEST_MESSAGES.items():
        if isinstance(exc, kind):
            return replacement
    if isinstance(exc, exceptions.PermissionDenied) and message.startswith("CSRF Failed"):
        return CSRF_MESSAGE
    # DRF's bare defaults, when a view raises one without a message of its own.
    if isinstance(exc, exceptions.NotFound) and message == str(exceptions.NotFound.default_detail):
        return DEFAULT_MESSAGES[404]
    if isinstance(exc, exceptions.PermissionDenied) and message == str(
        exceptions.PermissionDenied.default_detail
    ):
        return DEFAULT_MESSAGES[403]
    if not PERSIAN_LETTERS.search(message):
        return DEFAULT_MESSAGES.get(status_code, DEFAULT_MESSAGES[400])
    return message


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

    code = getattr(exc, "default_code", "error")
    if isinstance(detail, dict) and isinstance(detail.get("detail"), exceptions.ErrorDetail):
        code = detail["detail"].code

    if isinstance(exc, exceptions.ValidationError):
        translated = _translate(detail)
        if isinstance(translated, dict):
            errors = translated
        message = _flatten_detail(translated)
    else:
        raw = detail["detail"] if isinstance(detail, dict) and "detail" in detail else detail
        reason = _flatten_detail(raw)
        message = _request_message(exc, reason, status_code)
        if message == CSRF_MESSAGE:
            code = "csrf_failed"
            # The person sees one sentence whatever the cause; the log keeps
            # which it was -- a missing cookie, a stale token, a foreign
            # origin -- since DRF itself logs none of them.
            request = context.get("request")
            logger.warning("CSRF check failed on %s: %s", getattr(request, "path", "?"), reason)

    if not message:
        message = DEFAULT_MESSAGES.get(status_code, DEFAULT_MESSAGES[400])

    response.data = {"detail": message, "code": code, "errors": errors}
    return response
