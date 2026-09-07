from rest_framework import serializers

from apps.users.models import (
    STALE_AFTER_DAYS_MAX,
    STALE_AFTER_DAYS_MIN,
    User,
)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class UserSerializer(serializers.ModelSerializer):
    """The authenticated user as the client sees themselves.

    `display_name` is what the sidebar and the dashboard greeting show; it
    falls back to the username when no first name is set.
    """

    display_name = serializers.CharField(read_only=True)
    is_telegram_linked = serializers.BooleanField(read_only=True)

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
        ]
        read_only_fields = [
            "id",
            "username",
            "display_name",
            "is_telegram_linked",
            "telegram_linked_at",
        ]
        extra_kwargs = {
            "stale_after_days": {
                "min_value": STALE_AFTER_DAYS_MIN,
                "max_value": STALE_AFTER_DAYS_MAX,
            }
        }
