import hmac
import logging
from typing import ClassVar

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView
from telegram import Update

from apps.telegrambot import handlers, services
from apps.telegrambot.throttling import WebhookRateThrottle
from apps.users.permissions import IsSiteOwner
from apps.users.serializers import UserSerializer

logger = logging.getLogger(__name__)

# Telegram echoes the secret given to setWebhook in this header.
SECRET_HEADER = "HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN"


def _link_payload(request: Request) -> dict:
    token = services.active_link_token(user=request.user)
    return {
        "is_linked": request.user.is_telegram_linked,
        "linked_at": request.user.telegram_linked_at,
        "link": token.deep_link if token else None,
        "expires_at": token.expires_at if token else None,
    }


class TelegramLinkView(APIView):
    """The Telegram section of the settings page.

    GET reports the current connection, POST issues a fresh one-time link and
    DELETE drops the connection. The bot serves the site's owner alone, so no
    other account gets this far.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated, IsSiteOwner]

    def get(self, request: Request) -> Response:
        return Response(_link_payload(request))

    def post(self, request: Request) -> Response:
        services.issue_link_token(user=request.user)
        return Response(_link_payload(request), status=status.HTTP_201_CREATED)

    def delete(self, request: Request) -> Response:
        services.unlink(user=request.user)
        return Response(UserSerializer(request.user).data)


class TelegramWebhookView(APIView):
    """Where Telegram delivers updates.

    Unauthenticated by necessity: Telegram carries no session and no CSRF
    token. What stands in for authentication is the secret handed to
    setWebhook and echoed back in a header, compared in constant time.

    The response is always 200. Telegram retries anything else, so a bad
    update would be redelivered forever; failures are logged instead.
    """

    authentication_classes: ClassVar[list] = []
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]
    throttle_classes: ClassVar[list[type[BaseThrottle]]] = [WebhookRateThrottle]

    def post(self, request: Request) -> Response:
        if not self._secret_matches(request):
            logger.warning("Rejected a Telegram update with a bad secret header")
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            # Parsed without a client: the handlers reply through
            # apps.telegrambot.bot, never through an object's shortcut methods,
            # so nothing on the update needs one.
            update = Update.de_json(request.data)
        except Exception:
            logger.exception("Could not parse a Telegram update")
            return Response({"ok": True})

        handlers.handle_update(update)
        return Response({"ok": True})

    def _secret_matches(self, request: Request) -> bool:
        expected = settings.TELEGRAM_WEBHOOK_SECRET
        if not expected:
            # Refusing everything is the safe reading of "not configured".
            return False

        return hmac.compare_digest(request.META.get(SECRET_HEADER, ""), expected)
