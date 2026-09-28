"""The owner's user panel: the accounts, and the special ones made here.

Special accounts have no public sign-up. The owner makes them from this panel
or turns a regular account into one, and back again; the kind of account is
decided by which endpoint is called, never by anything in the request.
"""

from typing import ClassVar

from django.db.models import QuerySet
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.ideas.selectors import count_ideas
from apps.users import services
from apps.users.models import User
from apps.users.permissions import IsSiteOwner
from apps.users.serializers import NewAccountSerializer, PanelUserSerializer


class UserPanelViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """GET lists the accounts, POST makes a special one, `upgrade` makes a
    regular one special and `downgrade` makes a special one regular.

    The owner's alone: a 403 for everyone else, anonymous visitors included.
    The owner's own account and guests are not listed, so neither can have
    its kind changed here.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated, IsSiteOwner]

    def get_queryset(self) -> QuerySet[User]:
        # Guests are not accounts, and the owner is not managed from here.
        return (
            User.objects.filter(is_guest=False, is_superuser=False)
            .annotate(idea_total=count_ideas())
            .order_by("-date_joined", "-id")
        )

    def get_serializer_class(self) -> type[BaseSerializer]:
        return NewAccountSerializer if self.action == "create" else PanelUserSerializer

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = NewAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = services.create_special_user(**serializer.validated_data)
        return Response(PanelUserSerializer(user).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def upgrade(self, request: Request, pk: str | None = None) -> Response:
        """Turns a regular account into a special one."""
        user = services.make_special(user=self.get_object())
        return Response(PanelUserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def downgrade(self, request: Request, pk: str | None = None) -> Response:
        """Turns a special account back into a regular one."""
        user = services.make_regular(user=self.get_object())
        return Response(PanelUserSerializer(user).data)
