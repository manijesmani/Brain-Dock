import uuid
from pathlib import PurePath

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# Bounds for the "stale idea" threshold, mirroring the stepper in the design
# reference (BrainDock.dc.html), which clamps the value to this range.
STALE_AFTER_DAYS_MIN = 1
STALE_AFTER_DAYS_MAX = 90
STALE_AFTER_DAYS_DEFAULT = 14

# What a guest is called wherever a name is shown. The username of a guest
# is random and means nothing to anyone.
GUEST_DISPLAY_NAME = "مهمان"


def avatar_upload_path(instance: "User", filename: str) -> str:
    # A new name for every picture, so the URL changes with it and a browser
    # holding the old one in its cache never shows it again.
    extension = PurePath(filename).suffix.lower()
    return f"avatars/{instance.pk}/{uuid.uuid4().hex}{extension}"


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

    # Private like the attachments: served only to its owner, through
    # AvatarView. Checked, squared and resized by apps.users.avatar first.
    avatar = models.FileField(
        upload_to=avatar_upload_path,
        blank=True,
        verbose_name="تصویر پروفایل",
    )

    # Someone using the app without having signed up. The app opens straight
    # into an account like this, so nothing needs a login to try; signing up
    # later turns the same row into a real account and keeps everything in
    # it. See apps.users.services.
    is_guest = models.BooleanField(default=False, verbose_name="مهمان")

    # A special account: no idea limit, attachments allowed. Only the owner
    # makes one, from the user panel in settings; nobody can sign up as one.
    # See apps.users.plans.
    is_premium = models.BooleanField(default=False, verbose_name="کاربر ویژه")

    class Meta(AbstractUser.Meta):
        db_table = "users_user"
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

    def __str__(self) -> str:
        return self.get_username()

    @property
    def display_name(self) -> str:
        """The name shown in the sidebar and the dashboard greeting."""
        if self.is_guest:
            return GUEST_DISPLAY_NAME
        return self.first_name.strip() or self.get_username()

    @property
    def is_site_owner(self) -> bool:
        """Whether this is the person who runs the site.

        That is the superuser created at deployment. Signing up can never make
        one, so the owner's extras -- the Telegram bot above all -- are out of
        reach of every other account.
        """
        return self.is_superuser

    @property
    def is_telegram_linked(self) -> bool:
        return self.telegram_chat_id is not None


class DeviceSession(models.Model):
    """A browser signed in to an account: one per session.

    What the account holder sees under «دستگاه‌های فعال» in settings, and
    signs out from there. Tied to Django's own session row, so it goes the
    moment the session does -- on signing out, on expiry, or when it is
    signed out from another device. Guests are not recorded: a guest has only
    the one browser. See apps.users.devices.
    """

    session = models.OneToOneField(
        "sessions.Session",
        on_delete=models.CASCADE,
        related_name="device",
        verbose_name="نشست",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="devices",
        verbose_name="کاربر",
    )
    user_agent = models.CharField(max_length=512, blank=True, verbose_name="مرورگر")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="آدرس IP")
    # Empty for the sessions that were already signed in when this table
    # came about: when they began was never written down.
    signed_in_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان ورود")
    last_seen_at = models.DateTimeField(null=True, blank=True, verbose_name="آخرین استفاده")

    class Meta:
        verbose_name = "دستگاه فعال"
        verbose_name_plural = "دستگاه‌های فعال"

    def __str__(self) -> str:
        return f"{self.user} · {self.ip_address or '?'}"
