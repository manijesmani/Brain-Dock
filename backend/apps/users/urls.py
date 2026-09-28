from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.users.views import (
    AvatarView,
    CsrfView,
    CurrentUserView,
    DeviceViewSet,
    GuestView,
    LoginView,
    LogoutView,
    SignupView,
)

app_name = "users"

router = SimpleRouter()
router.register("devices", DeviceViewSet, basename="device")

urlpatterns = [
    path("csrf/", CsrfView.as_view(), name="csrf"),
    path("login/", LoginView.as_view(), name="login"),
    path("guest/", GuestView.as_view(), name="guest"),
    path("signup/", SignupView.as_view(), name="signup"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path("me/avatar/", AvatarView.as_view(), name="avatar"),
    *router.urls,
]
