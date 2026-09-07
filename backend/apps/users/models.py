from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# Bounds for the "stale idea" threshold, mirroring the stepper in the design
# reference (BrainDock.dc.html), which clamps the value to this range.
STALE_AFTER_DAYS_MIN = 1
STALE_AFTER_DAYS_MAX = 90
STALE_AFTER_DAYS_DEFAULT = 14


class User(AbstractUser):
    """The project's user.

    Declared as AUTH_USER_MODEL from the very first migration, because Django
    cannot swap the user model afterwards without dropping the database.

    Only genuinely per-user, server-side state lives here. Presentation
    preferences such as the colour theme are kept client-side.
    """

    # Telegram chat ids exceed the 32-bit range, so BigInteger is required.
    telegram_chat_id = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        verbose_name="شناسهٔ چت تلگرام",
    )
    telegram_linked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان اتصال تلگرام",
    )

    # How long an idea may sit untouched before it counts as stale. Read by the
    # periodic stale-idea job in phase 7.
    stale_after_days = models.PositiveSmallIntegerField(
        default=STALE_AFTER_DAYS_DEFAULT,
        validators=[
            MinValueValidator(STALE_AFTER_DAYS_MIN),
            MaxValueValidator(STALE_AFTER_DAYS_MAX),
        ],
        verbose_name="آستانهٔ ایدهٔ راکد (روز)",
    )

    class Meta(AbstractUser.Meta):
        db_table = "users_user"
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

    def __str__(self) -> str:
        return self.get_username()

    @property
    def display_name(self) -> str:
        """The name shown in the sidebar and the dashboard greeting."""
        return self.first_name.strip() or self.get_username()

    @property
    def is_telegram_linked(self) -> bool:
        return self.telegram_chat_id is not None
