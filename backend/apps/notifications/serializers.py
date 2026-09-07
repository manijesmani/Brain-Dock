from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "text", "idea", "is_read", "read_at", "created_at"]
        read_only_fields = ["id", "kind", "text", "idea", "read_at", "created_at"]
