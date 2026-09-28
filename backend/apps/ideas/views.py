from typing import ClassVar

from django.db.models import QuerySet
from rest_framework import mixins, viewsets
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from apps.ideas import selectors, services
from apps.ideas.filters import IdeaFilter
from apps.ideas.models import Category, Idea, IdeaStatus, Tag
from apps.ideas.serializers import (
    CategorySerializer,
    IdeaListSerializer,
    IdeaSerializer,
    TagSerializer,
    TrashedIdeaSerializer,
)
from core.permissions import IsOwner


class OwnedModelViewSet(viewsets.ModelViewSet):
    """Base for every viewset in this app.

    Ownership is enforced by narrowing the queryset, not by checking after the
    fact, so a record belonging to somebody else is a 404 rather than a 403 --
    the existence of another user's data is not disclosed. `IsOwner` stays on
    as a second barrier.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated, IsOwner]


class CategoryViewSet(OwnedModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self) -> QuerySet[Category]:
        # Django drops Meta.ordering from GROUP BY queries, so annotating
        # silently leaves the result unordered unless it is restated here.
        return (
            selectors.category_queryset(owner=self.request.user)
            .annotate(idea_count=selectors.count_ideas())
            .order_by("name")
        )

    def perform_create(self, serializer: BaseSerializer) -> None:
        serializer.instance = services.create_category(
            owner=self.request.user,
            name=serializer.validated_data["name"],
            color=serializer.validated_data.get("color", Category.color.field.default),
        )

    def perform_update(self, serializer: BaseSerializer) -> None:
        serializer.instance = services.update_category(
            category=serializer.instance,
            **serializer.validated_data,
        )


class TagViewSet(OwnedModelViewSet):
    serializer_class = TagSerializer

    def get_queryset(self) -> QuerySet[Tag]:
        return (
            selectors.tag_queryset(owner=self.request.user)
            .annotate(idea_count=selectors.count_ideas())
            .order_by("name")
        )

    def perform_create(self, serializer: BaseSerializer) -> None:
        serializer.save(owner=self.request.user)


class IdeaViewSet(OwnedModelViewSet):
    serializer_class = IdeaSerializer
    filterset_class = IdeaFilter

    def get_queryset(self) -> QuerySet[Idea]:
        queryset = selectors.idea_queryset(owner=self.request.user)

        # The archive is a separate screen, so active and archived ideas are
        # never mixed in one listing. This is decided before the filterset
        # runs, which is why `archived` is not one of its fields.
        if self.action == "list":
            archived = self.request.query_params.get("archived") == "true"
            if archived:
                return queryset.filter(status=IdeaStatus.ARCHIVED)
            return queryset.exclude(status=IdeaStatus.ARCHIVED)

        return queryset

    def filter_queryset(self, queryset: QuerySet[Idea]) -> QuerySet[Idea]:
        # Filtering only makes sense for the listing; applying it to a detail
        # lookup would let a query parameter turn a fetch into a 404.
        if self.action != "list":
            return queryset
        return super().filter_queryset(queryset)

    def get_serializer_class(self) -> type[BaseSerializer]:
        if self.action == "list":
            return IdeaListSerializer
        return IdeaSerializer

    def perform_create(self, serializer: BaseSerializer) -> None:
        data = serializer.validated_data
        serializer.instance = services.create_idea(
            owner=self.request.user,
            title=data["title"],
            content=data.get("content"),
            category=data.get("category"),
            tag_names=data.get("tags", []),
            status=data.get("status", IdeaStatus.IDEA),
            priority=data.get("priority", Idea.priority.field.default),
        )

    def perform_update(self, serializer: BaseSerializer) -> None:
        data = dict(serializer.validated_data)
        if "tags" in data:
            data["tag_names"] = data.pop("tags")

        serializer.instance = services.update_idea(idea=serializer.instance, **data)

    def perform_destroy(self, instance: Idea) -> None:
        # Deleting moves the idea to the trash; only the trash deletes for good.
        services.trash_idea(idea=instance)

    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk: str | None = None) -> Response:
        idea = services.archive_idea(idea=self.get_object())
        return Response(self.get_serializer(idea).data, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def restore(self, request: Request, pk: str | None = None) -> Response:
        idea = services.restore_idea(idea=self.get_object())
        return Response(self.get_serializer(idea).data, status=http_status.HTTP_200_OK)


class TrashViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """The account's trash.

    GET lists the deleted ideas, `restore` takes one back out, and DELETE
    removes it for good. Each works on the requesting account's own trash
    alone: anyone else's idea -- or one that is not in the trash -- is a 404.
    """

    serializer_class = TrashedIdeaSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated, IsOwner]

    def get_queryset(self) -> QuerySet[Idea]:
        return selectors.trashed_idea_queryset(owner=self.request.user)

    def perform_destroy(self, instance: Idea) -> None:
        services.delete_idea(idea=instance)

    @action(detail=True, methods=["post"])
    def restore(self, request: Request, pk: str | None = None) -> Response:
        idea = services.untrash_idea(idea=self.get_object())
        return Response(IdeaSerializer(idea, context=self.get_serializer_context()).data)
