"""Account linking between a BrainDock user and a Telegram chat.

The bot itself arrives in phase 6; what lives here is the half the settings
page drives: issuing a one-time link and dropping an existing connection.
"""

from django.db import transaction
from django.utils import timezone

from apps.telegrambot.models import TOKEN_LIFETIME, TelegramLinkToken
from apps.users.models import User


@transaction.atomic
def issue_link_token(*, user: User) -> TelegramLinkToken:
    """Creates a fresh link, invalidating any earlier unused one.

    Only one live token per account: an old link left working would be a
    second, forgotten key to the same door.
    """
    TelegramLinkToken.objects.filter(user=user, used_at__isnull=True).update(
        expires_at=timezone.now()
    )

    return TelegramLinkToken.objects.create(
        user=user,
        expires_at=timezone.now() + TOKEN_LIFETIME,
    )


def active_link_token(*, user: User) -> TelegramLinkToken | None:
    return (
        TelegramLinkToken.objects.filter(
            user=user, used_at__isnull=True, expires_at__gt=timezone.now()
        )
        .order_by("-created_at")
        .first()
    )


@transaction.atomic
def unlink(*, user: User) -> User:
    """Disconnects the chat and revokes any outstanding link."""
    user.telegram_chat_id = None
    user.telegram_linked_at = None
    user.save(update_fields=["telegram_chat_id", "telegram_linked_at"])

    TelegramLinkToken.objects.filter(user=user, used_at__isnull=True).update(
        expires_at=timezone.now()
    )

    return user
