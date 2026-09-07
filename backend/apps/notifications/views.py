from typing import ClassVar

from django.db.models import QuerySet
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.notifications import services
from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer
from core.permissions import IsOwner


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Notifications are produced by the system and only ever read or removed."""

    serializer_class = NotificationSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated, IsOwner]

    def get_queryset(self) -> QuerySet[Notification]:
        queryset = services.notification_queryset(owner=self.request.user)

        if self.request.query_params.get("unread") == "true":
            queryset = queryset.filter(is_read=False)

        return queryset

    @action(detail=False, methods=["get"])
    def unread_count(self, request: Request) -> Response:
        """Backs the badge in the sidebar, which every screen shows."""
        return Response({"count": services.unread_count(owner=request.user)})

    @action(detail=True, methods=["post"])
    def read(self, request: Request, pk: str | None = None) -> Response:
        notification = services.mark_read(notification=self.get_object())
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"])
    def read_all(self, request: Request) -> Response:
        updated = services.mark_all_read(owner=request.user)
        return Response({"updated": updated})
