"""The periodic job behind the stale-idea alert.

This is deliberately not a reminder. A reminder is something the user set on
one idea; this is the product noticing, on its own, that ideas have gone
quiet. The two share nothing but the fact that both end in a notification.

It runs once a day rather than every minute, because "you have not touched
this in two weeks" does not become truer at a finer resolution.
"""

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.ideas.models import Idea
from apps.ideas.selectors import stale_idea_queryset
from apps.notifications.channels.base import ChannelUnavailableError, Message
from apps.notifications.channels.telegram import TelegramChannel
from apps.notifications.models import Notification, NotificationKind, StaleAlert
from apps.users.models import User
from core.formatting import to_persian_digits

logger = logging.getLogger(__name__)

# Enough to make the point without turning the message into a wall.
DIGEST_LIMIT = 10


def notification_text(idea: Idea, *, days: int) -> str:
    """The wording the design shows: «عنوان» N روز بدون تغییر مانده."""
    return f"«{idea.title}» {to_persian_digits(days)} روز بدون تغییر مانده"


def days_idle(idea: Idea) -> int:
    return max(0, (timezone.now() - idea.updated_at).days)


@shared_task(name="notifications.send_stale_digests")
def send_stale_digests() -> dict[str, int]:
    """Tells each user about ideas that have gone quiet since last time."""
    users = User.objects.filter(is_active=True)

    reported = 0
    reached = 0

    for user in users:
        ideas = _unreported_stale_ideas(user)
        if not ideas:
            continue

        _record(ideas)
        _notify_in_app(user, ideas)

        if _notify_telegram(user, ideas):
            reached += 1

        reported += len(ideas)

    if reported:
        logger.info("Reported %s stale idea(s) to %s user(s)", reported, reached)

    return {"ideas": reported, "telegram_deliveries": reached}


def _unreported_stale_ideas(user: User) -> list[Idea]:
    """Stale ideas the user has not already been told about.

    An idea whose alert predates its own last change has been edited since,
    so this is a fresh period of neglect and worth mentioning again.
    """
    return [
        idea
        for idea in stale_idea_queryset(owner=user).select_related("stale_alert")
        if not _already_reported(idea)
    ]


def _already_reported(idea: Idea) -> bool:
    alert = getattr(idea, "stale_alert", None)
    return alert is not None and alert.notified_at >= idea.updated_at


@transaction.atomic
def _record(ideas: list[Idea]) -> None:
    now = timezone.now()

    for idea in ideas:
        StaleAlert.objects.update_or_create(idea=idea, defaults={"notified_at": now})


def _notify_in_app(user: User, ideas: list[Idea]) -> None:
    """One row per idea, so each is clickable -- as the design draws it."""
    Notification.objects.bulk_create(
        Notification(
            owner=user,
            kind=NotificationKind.STALE,
            text=notification_text(idea, days=days_idle(idea)),
            idea=idea,
        )
        for idea in ideas
    )


def _notify_telegram(user: User, ideas: list[Idea]) -> bool:
    """One summary, which is what a chat wants instead of ten messages."""
    from apps.telegrambot import messages as telegram_messages

    channel = TelegramChannel()
    if not channel.is_available_for(user):
        return False

    try:
        channel.send(
            Message(
                recipient=user,
                text=telegram_messages.stale_digest(ideas[:DIGEST_LIMIT]),
            )
        )
    except ChannelUnavailableError as error:
        logger.warning("Stale digest not delivered to %s: %s", user.pk, error)
        return False

    return True
