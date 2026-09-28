from pathlib import PurePath
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from rest_framework import serializers

from apps.users import plans
from apps.users.devices import describe_user_agent
from apps.users.models import (
    STALE_AFTER_DAYS_MAX,
    STALE_AFTER_DAYS_MIN,
    DeviceSession,
    User,
)
from apps.users.services import GUEST_USERNAME_PREFIX
from core.formatting import to_persian_digits

# The password validators' complaints, keyed by their codes. Django's Persian
# catalogue lacks the plural form of the length message, so that one would
# arrive in English; the rest are worded here to match it and the app.
PASSWORD_MESSAGES = {
    "password_too_short": "رمز عبور باید دست‌کم {min_length} حرف باشد.",
    "password_too_common": "این رمز عبور خیلی رایج است؛ رمز دیگری انتخاب کن.",
    "password_entirely_numeric": "رمز عبور نباید فقط عدد باشد.",
    "password_too_similar": "رمز عبور خیلی شبیه نام کاربری است.",
}


def password_messages(error: DjangoValidationError) -> list[str]:
    messages: list[str] = []
    for item in error.error_list:
        template = PASSWORD_MESSAGES.get(item.code or "")
        if template is None:
            messages.extend(item.messages)
            continue
        params = {name: to_persian_digits(value) for name, value in (item.params or {}).items()}
        messages.append(template.format(**params))
    return messages


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


def required_text(label: str, **options: Any) -> serializers.CharField:
    """A text field whose "missing" and "empty" complaints are in Persian."""
    message = f"{label} را بنویس."
    return serializers.CharField(error_messages={"required": message, "blank": message}, **options)


class NewAccountSerializer(serializers.Serializer):
    """The form behind both signing up and the owner making a special account.

    There is deliberately no field for the kind of account: the view that
    uses the form decides it, so nothing a client sends can choose a role.
    """

    first_name = required_text("نام", max_length=150, trim_whitespace=True)
    username = required_text("نام کاربری", max_length=150, trim_whitespace=True)
    password = required_text("رمز عبور", max_length=128, trim_whitespace=False)

    def validate_username(self, value: str) -> str:
        try:
            UnicodeUsernameValidator()(value)
        except DjangoValidationError:
            raise serializers.ValidationError(
                "نام کاربری فقط می‌تواند حرف، عدد و نشانه‌های @ . + - _ داشته باشد."
            ) from None

        # Compared without regard to case, so nobody can sign up as a
        # look-alike of an existing name -- the owner's included.
        if value.lower().startswith(GUEST_USERNAME_PREFIX) or (
            User.objects.filter(username__iexact=value).exists()
        ):
            raise serializers.ValidationError("این نام کاربری گرفته شده است.")

        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        # Checked against the new names too, so the password cannot simply
        # repeat them.
        candidate = User(username=attrs["username"], first_name=attrs["first_name"])
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": password_messages(error)}) from None

        return attrs


class PanelUserSerializer(serializers.ModelSerializer):
    """An account as the owner's user panel lists it."""

    display_name = serializers.CharField(read_only=True)
    plan = serializers.SerializerMethodField()
    idea_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "display_name",
            "plan",
            "idea_count",
            "date_joined",
        ]
        read_only_fields = fields

    def get_plan(self, user: User) -> str:
        return plans.plan_of(user)

    def get_idea_count(self, user: User) -> int:
        # Counted in the listing's own query where it can be; see the panel view.
        counted = getattr(user, "idea_total", None)
        return counted if counted is not None else user.ideas.outside_trash().count()


class UserSerializer(serializers.ModelSerializer):
    """The authenticated user as the client sees themselves.

    `display_name` is what the sidebar and the dashboard greeting show; it
    falls back to the username when no first name is set.

    The plan and what it allows travel with the account, so the interface can
    lock a tool or show a limit before anyone runs into it. The server still
    enforces every one of them; see apps.users.plans.
    """

    display_name = serializers.CharField(read_only=True)
    is_telegram_linked = serializers.BooleanField(read_only=True)
    avatar_url = serializers.SerializerMethodField()
    plan = serializers.SerializerMethodField()
    idea_limit = serializers.SerializerMethodField()
    idea_count = serializers.SerializerMethodField()
    can_attach_media = serializers.SerializerMethodField()
    can_use_telegram = serializers.SerializerMethodField()
    can_manage_users = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "display_name",
            "stale_after_days",
            "is_telegram_linked",
            "telegram_linked_at",
            "avatar_url",
            "plan",
            "idea_limit",
            "idea_count",
            "can_attach_media",
            "can_use_telegram",
            "can_manage_users",
        ]
        read_only_fields = [
            "id",
            "username",
            "display_name",
            "is_telegram_linked",
            "telegram_linked_at",
            "avatar_url",
        ]
        extra_kwargs = {
            "stale_after_days": {
                "min_value": STALE_AFTER_DAYS_MIN,
                "max_value": STALE_AFTER_DAYS_MAX,
            }
        }

    def get_avatar_url(self, user: User) -> str | None:
        if not user.avatar:
            return None
        # The file name changes with every upload, so it doubles as a version
        # the browser can cache against.
        return f"{reverse('users:avatar')}?v={PurePath(user.avatar.name).stem}"

    def get_plan(self, user: User) -> str:
        return plans.plan_of(user)

    def get_idea_limit(self, user: User) -> int | None:
        return plans.idea_limit(user)

    def get_idea_count(self, user: User) -> int:
        # Archived ideas included, the trash not: what the limit counts.
        return user.ideas.outside_trash().count()

    def get_can_attach_media(self, user: User) -> bool:
        return plans.can_attach_media(user)

    def get_can_use_telegram(self, user: User) -> bool:
        return plans.can_use_telegram(user)

    def get_can_manage_users(self, user: User) -> bool:
        return plans.can_manage_users(user)


class AvatarUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class DeviceSerializer(serializers.ModelSerializer):
    """A signed-in device, as «دستگاه‌های فعال» lists it."""

    name = serializers.SerializerMethodField()
    kind = serializers.SerializerMethodField()
    current = serializers.SerializerMethodField()

    class Meta:
        model = DeviceSession
        fields = [
            "id",
            "name",
            "kind",
            "user_agent",
            "ip_address",
            "signed_in_at",
            "last_seen_at",
            "current",
        ]
        read_only_fields = fields

    def get_name(self, device: DeviceSession) -> str:
        return describe_user_agent(device.user_agent).name

    def get_kind(self, device: DeviceSession) -> str:
        return describe_user_agent(device.user_agent).kind

    def get_current(self, device: DeviceSession) -> bool:
        # The device this very request came from.
        return device.session_id == self.context["request"].session.session_key
