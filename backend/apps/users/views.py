from typing import ClassVar

from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView

from apps.users.serializers import LoginSerializer, UserSerializer
from apps.users.throttling import LoginRateThrottle


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Hands the SPA a CSRF cookie before it attempts its first write.

    The frontend calls this once on start-up; Django sets `csrftoken` and the
    axios instance mirrors it into the `X-CSRFToken` header from then on.
    """

    authentication_classes: ClassVar[list] = []
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"csrf_token": get_token(request)})


class LoginView(APIView):
    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]
    throttle_classes: ClassVar[list[type[BaseThrottle]]] = [LoginRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )

        # A single message for both a wrong username and a wrong password, so
        # the endpoint cannot be used to discover which accounts exist.
        if user is None:
            return Response(
                {
                    "detail": "نام کاربری یا رمز عبور درست نیست.",
                    "code": "invalid_credentials",
                    "errors": None,
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(UserSerializer(request.user).data)

    def patch(self, request: Request) -> Response:
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
