"""Account linking between a BrainDock user and a Telegram chat.

Settings issues private one-time links and lets registered accounts drop
an existing connection. Guests cannot access these operations.
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
    user = User.objects.select_for_update().get(pk=user.pk)
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
    user = User.objects.select_for_update().get(pk=user.pk)
    user.telegram_chat_id = None
    user.telegram_linked_at = None
    user.save(update_fields=["telegram_chat_id", "telegram_linked_at"])

    TelegramLinkToken.objects.filter(user=user, used_at__isnull=True).update(
        expires_at=timezone.now()
    )

    return user
