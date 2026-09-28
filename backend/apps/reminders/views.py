from typing import ClassVar

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.reminders import selectors, services
from apps.reminders.models import Reminder
from apps.reminders.serializers import ReminderSerializer, SnoozeSerializer
from core.permissions import IsOwner


class ReminderViewSet(viewsets.ModelViewSet):
    serializer_class = ReminderSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated, IsOwner]

    def get_queryset(self) -> QuerySet[Reminder]:
        # A reminder on an idea in the trash is kept, but out of sight and
        # silent until the idea is taken back out.
        queryset = Reminder.objects.filter(
            owner=self.request.user, idea__deleted_at__isnull=True
        ).select_related("idea", "idea__category", "owner")

        window = self.request.query_params.get("window")
        if window in {"today", "week"}:
            # Both windows are decided by evaluating each rule rather than by
            # comparing `next_run_at`, because today's agenda includes a slot
            # that has already been delivered. See apps.reminders.selectors.
            active = list(queryset.filter(is_active=True).order_by("next_run_at"))
            chosen = (
                selectors.due_today(active)
                if window == "today"
                else selectors.due_this_week(active)
            )
            return queryset.filter(pk__in=[item.pk for item in chosen]).order_by("next_run_at")

        return queryset.order_by("next_run_at")

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
        form = SnoozeSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        reminder = services.snooze(
            reminder=self.get_object(), minutes=form.validated_data["minutes"]
        )
        return Response(self.get_serializer(reminder).data)
