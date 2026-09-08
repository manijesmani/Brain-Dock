from typing import ClassVar

from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.telegrambot import services
from apps.users.serializers import UserSerializer


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
    DELETE drops the connection.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(_link_payload(request))

    def post(self, request: Request) -> Response:
        services.issue_link_token(user=request.user)
        return Response(_link_payload(request), status=status.HTTP_201_CREATED)

    def delete(self, request: Request) -> Response:
        services.unlink(user=request.user)
        return Response(UserSerializer(request.user).data)
