import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel

# Long enough that guessing is hopeless, short enough to sit in a t.me link.
TOKEN_BYTES = 12

# The link is meant to be used immediately, from the settings page to the bot.
TOKEN_LIFETIME = timedelta(minutes=30)


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


class TelegramLinkToken(TimeStampedModel):
    """A single-use secret that binds a Telegram chat to an account.

    Kept as its own model rather than a column on the user: a token is an
    event with a lifetime and an outcome, and modelling it as user state would
    lose the record of when linking happened and leave a live secret sitting
    on the account forever.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="telegram_link_tokens",
        verbose_name="کاربر",
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_token,
        editable=False,
        verbose_name="توکن",
    )
    expires_at = models.DateTimeField(verbose_name="زمان انقضا")
    used_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان استفاده")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "توکن اتصال تلگرام"
        verbose_name_plural = "توکن‌های اتصال تلگرام"
        indexes = [models.Index(fields=["token"])]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.token[:6]}…"

    @property
    def is_usable(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()

    @property
    def deep_link(self) -> str:
        """The t.me address the user opens to hand the token to the bot."""
        username = settings.TELEGRAM_BOT_USERNAME
        return f"t.me/{username}?start={self.token}"
