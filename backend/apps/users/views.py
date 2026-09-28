from pathlib import PurePath
from typing import ClassVar

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db.models import QuerySet
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import mixins, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView

from apps.users import devices, services
from apps.users.avatar import CONTENT_TYPES
from apps.users.models import DeviceSession
from apps.users.permissions import HasAccount
from apps.users.serializers import (
    AvatarUploadSerializer,
    DeviceSerializer,
    LoginSerializer,
    NewAccountSerializer,
    UserSerializer,
)
from apps.users.throttling import GuestRateThrottle, LoginRateThrottle, SignupRateThrottle
from core.files import private_file_response

# Guests have no password, so they are signed in without `authenticate`,
# which is what normally names the backend.
SESSION_BACKEND = "django.contrib.auth.backends.ModelBackend"


def require_csrf(request: Request) -> None:
    """Checks the CSRF token even when nobody is signed in.

    DRF checks it only for a session that is already signed in. The views
    below change who is signed in, so without this another site could sign a
    visitor into an account of its choosing and read what they write there.
    """
    SessionAuthentication().enforce_csrf(request)


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
        require_csrf(request)
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

        # Signing in from a guest session leaves the guest behind, with its
        # ideas kept in the database as everyone's are. Only signing up
        # carries a guest's ideas into an account.
        login(request, user)
        return Response(UserSerializer(user).data)


class GuestView(APIView):
    """Signs a first-time visitor into a new guest account.

    This is what makes the app usable without an account: the client calls
    it when it finds no session, and from then on the guest works exactly
    like anyone else, within the limits in apps.users.plans.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]
    throttle_classes: ClassVar[list[type[BaseThrottle]]] = [GuestRateThrottle]

    def post(self, request: Request) -> Response:
        require_csrf(request)

        # Already signed in, as a guest or otherwise: nothing to start.
        if request.user.is_authenticated:
            return Response(UserSerializer(request.user).data)

        user = services.create_guest()
        login(request, user, backend=SESSION_BACKEND)
        # The cookie is the only way back to a guest's ideas, so it is kept far
        # longer than an account's. Signing up or in starts a normal session.
        request.session.set_expiry(settings.GUEST_SESSION_AGE)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class SignupView(APIView):
    """Creates a regular account with a name, a username and a password.

    Signed in as a guest, the guest itself becomes the account, keeping
    everything written so far. Special accounts are never made here: only
    the owner makes those, from the user panel.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [AllowAny]
    throttle_classes: ClassVar[list[type[BaseThrottle]]] = [SignupRateThrottle]

    def post(self, request: Request) -> Response:
        require_csrf(request)

        current = request.user if request.user.is_authenticated else None
        if current is not None and not current.is_guest:
            return Response(
                {
                    "detail": "با یک حساب وارد شده‌ای. برای ساختن حساب تازه اول خارج شو.",
                    "code": "already_signed_up",
                    "errors": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = NewAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = services.sign_up(guest=current, **serializer.validated_data)
        # Signing in again starts a new session: the password is new, and a
        # session that was a guest's should not carry over into an account.
        login(request, user, backend=SESSION_BACKEND)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


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


class AvatarView(APIView):
    """The signed-in user's profile picture: shown, replaced or removed.

    There is only ever the requester's own picture here, so the session is
    the whole of the access check.
    """

    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated]
    parser_classes: ClassVar[list] = [MultiPartParser, FormParser]

    def get(self, request: Request) -> HttpResponse:
        avatar = request.user.avatar
        if not avatar:
            return Response(
                {"detail": "تصویر پروفایلی ثبت نشده.", "code": "not_found", "errors": None},
                status=status.HTTP_404_NOT_FOUND,
            )

        name = PurePath(avatar.name)
        return private_file_response(
            file_field=avatar,
            content_type=CONTENT_TYPES.get(name.suffix, "application/octet-stream"),
            filename=name.name,
        )

    def post(self, request: Request) -> Response:
        # A profile picture belongs to a profile, which a guest does not have.
        if request.user.is_guest:
            raise PermissionDenied("برای گذاشتن تصویر پروفایل اول یک حساب بساز.")

        serializer = AvatarUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_avatar(user=request.user, upload=serializer.validated_data["file"])
        return Response(UserSerializer(request.user).data)

    def delete(self, request: Request) -> Response:
        services.remove_avatar(user=request.user)
        return Response(UserSerializer(request.user).data)


class DeviceViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """«دستگاه‌های فعال»: where the account is signed in, and signing out there.

    GET lists the devices, this one first. DELETE signs one out -- any but
    this one, which signs out with the ordinary «خروج». `sign-out-others`
    signs out all the rest at once. Each only ever reaches the requester's
    own devices; a guest has none and gets a 403.
    """

    serializer_class = DeviceSerializer
    permission_classes: ClassVar[list[type[BasePermission]]] = [IsAuthenticated, HasAccount]
    # A handful at most, so all of them at once.
    pagination_class = None

    def get_queryset(self) -> QuerySet[DeviceSession]:
        return DeviceSession.objects.filter(user=self.request.user)

    def list(self, request: Request, *args: object, **kwargs: object) -> Response:
        current = request.session.session_key
        found = devices.active_devices(request.user)
        found.sort(key=lambda device: device.session_id != current)
        return Response(self.get_serializer(found, many=True).data)

    def perform_destroy(self, instance: DeviceSession) -> None:
        if instance.session_id == self.request.session.session_key:
            raise ValidationError("برای خروج از همین دستگاه، از دکمهٔ «خروج» استفاده کن.")
        devices.sign_out_device(instance)

    @action(detail=False, methods=["post"], url_path="sign-out-others")
    def sign_out_others(self, request: Request) -> Response:
        count = devices.sign_out_other_devices(request.user, keep=request.session.session_key)
        return Response({"signed_out": count})
