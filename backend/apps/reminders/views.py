from typing import ClassVar

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.reminders import services
from apps.reminders.models import Reminder
from apps.reminders.serializers import ReminderSerializer
from core.permissions import IsOwner


class ReminderViewSet(viewsets.ModelViewSet):
    serializer_class = ReminderSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated, IsOwner]

    def get_queryset(self) -> QuerySet[Reminder]:
        return Reminder.objects.filter(owner=self.request.user).select_related("idea", "owner")

    def perform_create(self, serializer: BaseSerializer) -> None:
        data = dict(serializer.validated_data)
        idea = data.pop("idea")
        serializer.instance = services.set_reminder(idea=idea, **data)

    def perform_update(self, serializer: BaseSerializer) -> None:
        data = dict(serializer.validated_data)
        idea = data.pop("idea", serializer.instance.idea)
        serializer.instance = services.set_reminder(idea=idea, **data)

    @action(detail=True, methods=["post"])
    def pause(self, request: Request, pk: str | None = None) -> Response:
        """Silences the reminder without discarding its configuration."""
        reminder = services.set_active(reminder=self.get_object(), is_active=False)
        return Response(self.get_serializer(reminder).data)

    @action(detail=True, methods=["post"])
    def resume(self, request: Request, pk: str | None = None) -> Response:
        reminder = services.set_active(reminder=self.get_object(), is_active=True)
        return Response(self.get_serializer(reminder).data)

    @action(detail=True, methods=["post"])
    def snooze(self, request: Request, pk: str | None = None) -> Response:
        """Pushes the next firing back by an hour, as the bot button does."""
        minutes = int(request.data.get("minutes", 60))
        reminder = services.snooze(reminder=self.get_object(), minutes=minutes)
        return Response(self.get_serializer(reminder).data)
