from typing import ClassVar

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connection
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

HEALTH_CACHE_KEY = "braindock:health"


class HealthView(APIView):
    """Liveness probe for the API and its backing services.

    Deliberately unauthenticated: the deployment's health check runs before any
    session exists.
    """

    authentication_classes: ClassVar[list] = []
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]

    def get(self, request: Request) -> Response:
        database_status = self._check_database()
        cache_status = self._check_cache()

        checks = {"database": database_status, "cache": cache_status}
        overall = "ok" if all(value == "ok" for value in checks.values()) else "error"

        return Response(
            {"status": overall, **checks, "version": settings.APP_VERSION},
            status=(status.HTTP_200_OK if overall == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE),
        )

    def _check_database(self) -> str:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            return "error"
        return "ok"

    def _check_cache(self) -> str:
        """Round-trips a value through the cache.

        Redis backs both the login throttle and the Celery broker, so an
        unreachable cache means reminders have stopped firing -- worth
        surfacing even though the API itself would still answer.
        """
        try:
            cache.set(HEALTH_CACHE_KEY, "ok", timeout=10)
            if cache.get(HEALTH_CACHE_KEY) != "ok":
                return "error"
        # A broad catch on purpose: any backend failure, of any kind, is
        # a failed health check.
        except Exception:
            return "error"
        return "ok"


class SiteView(APIView):
    """What the interface needs to know about this site before any session.

    Deliberately unauthenticated: the sign-up page shows it to visitors. Only
    what is meant to be public belongs here.
    """

    authentication_classes: ClassVar[list] = []
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]

    def get(self, request: Request) -> Response:
        from apps.ideas.attachments import (
            ALLOWED_IMAGE_FORMATS,
            AUDIO_FORMATS_TEXT,
            IMAGE_FORMATS_TEXT,
        )

        image_types = sorted({mime for _, mime in ALLOWED_IMAGE_FORMATS.values()})
        return Response(
            {
                # Where to ask the owner for a special account.
                "owner_telegram": settings.OWNER_TELEGRAM_USERNAME or None,
                # What may be uploaded, so the interface can say so before
                # anything is sent, and check it before a large file travels.
                "uploads": {
                    "image": {
                        "max_bytes": settings.MAX_IMAGE_UPLOAD_BYTES,
                        "types": image_types,
                        "formats": IMAGE_FORMATS_TEXT,
                    },
                    "audio": {
                        "max_bytes": settings.MAX_AUDIO_UPLOAD_BYTES,
                        "formats": AUDIO_FORMATS_TEXT,
                    },
                    "avatar": {
                        "max_bytes": settings.MAX_AVATAR_UPLOAD_BYTES,
                        "types": image_types,
                        "formats": IMAGE_FORMATS_TEXT,
                    },
                },
            }
        )
