"""Upload, listing and guarded delivery of attachment files.

MEDIA_ROOT is never published by the web server. A file is reachable only
through `AttachmentFileView`, which resolves the row inside the requesting
user's own queryset first. Once ownership holds, the bytes are handed to
Nginx via X-Accel-Redirect so Python is not tied up streaming them.
"""

from typing import ClassVar
from urllib.parse import quote

from django.conf import settings
from django.db.models import QuerySet
from django.http import FileResponse, HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ideas import selectors, services
from apps.ideas.models import Attachment
from apps.ideas.serializers import AttachmentSerializer, AttachmentUploadSerializer
from core.permissions import IsOwner


class AttachmentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Attachments are created and removed, never edited in place."""

    serializer_class = AttachmentSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated, IsOwner]
    parser_classes: ClassVar[list] = [MultiPartParser, FormParser]

    def get_queryset(self) -> QuerySet[Attachment]:
        queryset = selectors.attachment_queryset(owner=self.request.user)

        idea_id = self.request.query_params.get("idea")
        if idea_id:
            queryset = queryset.filter(idea_id=idea_id)

        return queryset

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = AttachmentUploadSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        attachment = services.create_attachment(
            idea=serializer.validated_data["idea"],
            upload=serializer.validated_data["file"],
            kind=serializer.validated_data["kind"],
        )

        return Response(
            AttachmentSerializer(attachment, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class BaseAttachmentFileView(APIView):
    """Shared ownership check and delivery mechanism."""

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]

    def get_attachment(self, request: Request, pk: int) -> Attachment | None:
        return selectors.attachment_queryset(owner=request.user).filter(pk=pk).first()

    def deliver(self, *, file_field: object, content_type: str, filename: str) -> HttpResponse:
        if settings.DEBUG:
            # No Nginx in front of the development server, so Django serves
            # the bytes itself.
            return FileResponse(file_field.open("rb"), content_type=content_type)

        response = HttpResponse(content_type=content_type)
        response["X-Accel-Redirect"] = f"{settings.MEDIA_INTERNAL_URL}{quote(file_field.name)}"
        # The name may be Persian, so it is sent in the RFC 5987 form only.
        response["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(filename)}"
        return response


class AttachmentFileView(BaseAttachmentFileView):
    def get(self, request: Request, pk: int) -> HttpResponse:
        attachment = self.get_attachment(request, pk)
        if attachment is None:
            return Response(
                {"detail": "پیوست پیدا نشد.", "code": "not_found", "errors": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        return self.deliver(
            file_field=attachment.file,
            content_type=attachment.content_type,
            filename=attachment.original_name or "attachment",
        )


class AttachmentThumbnailView(BaseAttachmentFileView):
    def get(self, request: Request, pk: int) -> HttpResponse:
        attachment = self.get_attachment(request, pk)
        if attachment is None or not attachment.thumbnail:
            return Response(
                {"detail": "بندانگشتی پیدا نشد.", "code": "not_found", "errors": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        return self.deliver(
            file_field=attachment.thumbnail,
            content_type=attachment.content_type,
            filename=attachment.original_name or "thumbnail",
        )
