from django.db.models import QuerySet
from django.utils import timezone

from apps.notifications.models import Notification
from apps.users.models import User


def unread_count(*, owner: User) -> int:
    return Notification.objects.filter(owner=owner, is_read=False).count()


def mark_read(*, notification: Notification) -> Notification:
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at", "updated_at"])
    return notification


def mark_all_read(*, owner: User) -> int:
    """Backs the «همه را خوانده‌شده کن» button. Returns how many changed."""
    return Notification.objects.filter(owner=owner, is_read=False).update(
        is_read=True, read_at=timezone.now(), updated_at=timezone.now()
    )


def notification_queryset(*, owner: User) -> QuerySet[Notification]:
    return Notification.objects.filter(owner=owner).select_related("idea")
