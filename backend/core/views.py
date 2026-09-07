from typing import ClassVar

from django.conf import settings
from django.db import DatabaseError, connection
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness probe for the API and its backing services.

    Deliberately unauthenticated: the deployment's health check runs before any
    session exists. Redis is not probed yet — it enters the stack in phase 4
    together with Celery, and a check for something unused would be noise.
    """

    authentication_classes: ClassVar[list] = []
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]

    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            database_status = "error"
        else:
            database_status = "ok"

        overall = "ok" if database_status == "ok" else "error"
        http_status = status.HTTP_200_OK if overall == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE

        return Response(
            {
                "status": overall,
                "database": database_status,
                "version": settings.APP_VERSION,
            },
            status=http_status,
        )
