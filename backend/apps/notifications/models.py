from django.db import models

from apps.ideas.models import Idea
from core.models import OwnedTimeStampedModel


class NotificationKind(models.TextChoices):
    """Matches the three icons the notification centre renders."""

    REMINDER = "reminder", "یادآوری"
    STALE = "stale", "ایدهٔ راکد"
    TELEGRAM_CAPTURE = "telegram_capture", "ثبت از تلگرام"


class Notification(OwnedTimeStampedModel):
    """One line in the notification centre.

    `text` is stored already rendered, in Persian and with Persian numerals.
    A notification describes something that happened at a particular moment,
    so re-deriving its wording later from data that has since changed would
    make it wrong.
    """

    kind = models.CharField(max_length=20, choices=NotificationKind, verbose_name="نوع")
    text = models.TextField(verbose_name="متن")

    # Null once the idea it referred to is deleted; the notification survives
    # so the history stays intact, it simply stops being a link.
    idea = models.ForeignKey(
        Idea,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
        verbose_name="ایده",
    )

    is_read = models.BooleanField(default=False, verbose_name="خوانده‌شده")
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "اعلان"
        verbose_name_plural = "اعلان‌ها"
        indexes = [
            # Backs the unread badge, which is read on every page.
            models.Index(
                fields=["owner"],
                condition=models.Q(is_read=False),
                name="notification_unread_idx",
            ),
            models.Index(fields=["owner", "-created_at"]),
        ]

    def __str__(self) -> str:
        return self.text[:60]
