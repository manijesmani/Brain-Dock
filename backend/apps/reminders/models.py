from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.ideas.models import Idea
from apps.reminders.recurrence import Schedule
from core.models import OwnedTimeStampedModel, TimeStampedModel


class ReminderRecurrence(models.TextChoices):
    """The recurrence rules offered by the reminder dialog.

    The dialog's fifth option, "بدون یادآوری", is the absence of a Reminder
    row rather than a value here -- the design models it as `rem: null`.
    """

    DAILY = "daily", "روزانه"
    WEEKLY = "weekly", "هفتگی"
    MONTHLY = "monthly", "ماهانه"
    EXACT = "exact", "تاریخ و ساعت دقیق"


class DeliveryChannel(models.TextChoices):
    IN_APP = "inapp", "داخل سایت"
    TELEGRAM = "telegram", "تلگرام"


class DeliveryStatus(models.TextChoices):
    PENDING = "pending", "در حال ارسال"
    SENT = "sent", "ارسال شد"
    FAILED = "failed", "ناموفق"


class Reminder(OwnedTimeStampedModel):
    """When an idea should come back to its owner.

    At most one per idea, matching the dialog, which edits a single reminder.

    `next_run_at` is the whole scheduling mechanism. No task is ever queued
    ahead of time: a single Celery Beat tick reads the rows whose next firing
    has arrived. A queue of future tasks would go stale on every restart,
    duplicate on every retry, and could not be cancelled reliably when the
    user edits the rule.
    """

    idea = models.OneToOneField(
        Idea,
        on_delete=models.CASCADE,
        related_name="reminder",
        verbose_name="ایده",
    )
    recurrence = models.CharField(
        max_length=8,
        choices=ReminderRecurrence,
        verbose_name="نوع تکرار",
    )

    hour = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(23)],
        default=9,
        verbose_name="ساعت",
    )
    minute = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(59)],
        default=0,
        verbose_name="دقیقه",
    )

    # Weekly only. Saturday is 0, as in jdatetime and in the design's chips.
    weekdays = ArrayField(
        models.PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(6)]),
        default=list,
        blank=True,
        verbose_name="روزهای هفته",
    )

    # Monthly only, 1-31 in the Jalali calendar. A month too short for the
    # chosen day fires on its last day instead.
    day_of_month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        verbose_name="روز ماه",
    )

    # One-off only. Stored as a Gregorian date; the Jalali form the user picked
    # is reconstructed for display, never stored.
    exact_date = models.DateField(null=True, blank=True, verbose_name="تاریخ")

    # The next firing, in UTC. Null means the rule has no future occurrence,
    # which only a one-off reminder in the past can produce.
    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Lets a reminder be silenced without losing its configuration.
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "یادآوری"
        verbose_name_plural = "یادآوری‌ها"
        indexes = [
            # The only index the beat tick needs: due and active, in one scan.
            models.Index(
                fields=["next_run_at"],
                condition=models.Q(is_active=True),
                name="reminder_due_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(hour__gte=0, hour__lte=23),
                name="reminder_hour_in_range",
            ),
            models.CheckConstraint(
                condition=models.Q(minute__gte=0, minute__lte=59),
                name="reminder_minute_in_range",
            ),
            # Each recurrence kind must carry the parameter it needs and no
            # other. Enforced in the database so a bad row cannot exist even if
            # it arrives through the admin or a data migration.
            models.CheckConstraint(
                condition=(
                    models.Q(recurrence="daily", day_of_month__isnull=True, exact_date__isnull=True)
                    | models.Q(
                        recurrence="weekly", day_of_month__isnull=True, exact_date__isnull=True
                    )
                    | models.Q(
                        recurrence="monthly",
                        day_of_month__isnull=False,
                        exact_date__isnull=True,
                    )
                    | models.Q(
                        recurrence="exact", day_of_month__isnull=True, exact_date__isnull=False
                    )
                ),
                name="reminder_parameters_match_recurrence",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.idea.title} ({self.get_recurrence_display()})"

    @property
    def schedule(self) -> Schedule:
        """The model's rule expressed in the form the calculator accepts."""
        return Schedule(
            kind=self.recurrence,
            hour=self.hour,
            minute=self.minute,
            weekdays=tuple(self.weekdays or ()),
            day_of_month=self.day_of_month,
            exact_date=self.exact_date,
        )


class ReminderDelivery(TimeStampedModel):
    """One attempt to deliver one firing of a reminder over one channel.

    The row is written before anything is sent, and the unique constraint is
    what makes delivery idempotent: a retried task or a second beat tick
    running concurrently collides on insert instead of notifying twice.
    """

    reminder = models.ForeignKey(
        Reminder,
        on_delete=models.CASCADE,
        related_name="deliveries",
        verbose_name="یادآوری",
    )
    # The slot being fulfilled, not the moment of sending. Two attempts at the
    # same slot are the same delivery however late either one runs.
    scheduled_for = models.DateTimeField(verbose_name="زمان سررسید")
    channel = models.CharField(max_length=10, choices=DeliveryChannel, verbose_name="کانال")
    status = models.CharField(
        max_length=8,
        choices=DeliveryStatus,
        default=DeliveryStatus.PENDING,
        verbose_name="وضعیت",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_for"]
        verbose_name = "ارسال یادآوری"
        verbose_name_plural = "ارسال‌های یادآوری"
        constraints = [
            models.UniqueConstraint(
                fields=["reminder", "scheduled_for", "channel"],
                name="unique_reminder_delivery",
            )
        ]

    def __str__(self) -> str:
        return f"{self.reminder_id} @ {self.scheduled_for:%Y-%m-%d %H:%M} ({self.channel})"
