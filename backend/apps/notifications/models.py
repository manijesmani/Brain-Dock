from django.db import models

from apps.ideas.models import Idea
from core.models import OwnedTimeStampedModel, TimeStampedModel


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


class StaleAlert(TimeStampedModel):
    """Records that an idea has already been reported as neglected.

    One row per idea rather than one per day, because the question is not
    "did we tell them today" but "did we tell them about *this* period of
    neglect". `notified_at` is compared against the idea's `updated_at`: the
    moment the user touches the idea, the alert falls behind it and the idea
    becomes eligible again once it goes stale afresh.

    Without this the digest would repeat the same list every single run.
    """

    idea = models.OneToOneField(
        Idea,
        on_delete=models.CASCADE,
        related_name="stale_alert",
        verbose_name="ایده",
    )
    notified_at = models.DateTimeField(verbose_name="زمان اطلاع")

    class Meta:
        ordering = ["-notified_at"]
        verbose_name = "هشدار ایدهٔ راکد"
        verbose_name_plural = "هشدارهای ایدهٔ راکد"

    def __str__(self) -> str:
        return f"{self.idea_id} @ {self.notified_at:%Y-%m-%d}"
