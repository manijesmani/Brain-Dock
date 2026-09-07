"""Creating, editing and firing reminders.

The scheduling contract is small and worth stating plainly:

  * A reminder is never queued ahead of time. Its next firing lives in
    `next_run_at`, and one periodic tick reads the rows that have come due.
  * Any change to the rule recomputes `next_run_at` immediately, so the tick
    never has to reason about stale configuration.
  * A firing is recorded before it is delivered. The unique constraint on
    (reminder, scheduled_for, channel) is what makes a retry or a concurrent
    tick harmless.
"""

import logging
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ideas.models import Idea
from apps.notifications.channels.base import ChannelUnavailableError, Message
from apps.notifications.channels.inapp import InAppChannel
from apps.reminders.messages import reminder_text
from apps.reminders.models import (
    DeliveryChannel,
    DeliveryStatus,
    Reminder,
    ReminderDelivery,
)
from apps.reminders.recurrence import compute_next_run

logger = logging.getLogger(__name__)

# Channels a reminder goes out over. Telegram joins this list in phase 6; the
# dispatcher already skips a channel a user cannot be reached on.
REMINDER_CHANNELS = [DeliveryChannel.IN_APP]


def refresh_next_run(reminder: Reminder, *, after: Any = None) -> Reminder:
    """Recomputes the next firing and deactivates a spent one-off reminder."""
    reference = after or timezone.now()
    reminder.next_run_at = compute_next_run(reminder.schedule, after=reference)

    if reminder.next_run_at is None:
        # Only a one-off whose moment has passed gets here. It stays on the
        # idea so the user can see what was set, but it will not fire again.
        reminder.is_active = False

    return reminder


@transaction.atomic
def set_reminder(*, idea: Idea, **fields: Any) -> Reminder:
    """Creates or replaces the reminder on an idea."""
    reminder, _ = Reminder.objects.update_or_create(
        idea=idea,
        defaults={"owner": idea.owner, **fields},
    )

    refresh_next_run(reminder)
    reminder.save(update_fields=["next_run_at", "is_active", "updated_at"])
    return reminder


@transaction.atomic
def clear_reminder(*, idea: Idea) -> None:
    """Removes the reminder entirely, as the dialog's «بدون یادآوری» does."""
    Reminder.objects.filter(idea=idea).delete()


def set_active(*, reminder: Reminder, is_active: bool) -> Reminder:
    """Silences or resumes a reminder without losing its configuration."""
    reminder.is_active = is_active

    if is_active:
        # While it was off, its slot passed. Resume from now rather than
        # firing immediately for a moment that is long gone.
        refresh_next_run(reminder)

    reminder.save(update_fields=["is_active", "next_run_at", "updated_at"])
    return reminder


def snooze(*, reminder: Reminder, minutes: int) -> Reminder:
    """Pushes the next firing back, for the bot's «یک ساعت بعد» button."""
    reminder.next_run_at = timezone.now() + timezone.timedelta(minutes=minutes)
    reminder.is_active = True
    reminder.save(update_fields=["next_run_at", "is_active", "updated_at"])
    return reminder


def deliver_reminder(*, reminder: Reminder, scheduled_for: Any) -> list[ReminderDelivery]:
    """Delivers one firing over every channel, exactly once each.

    Returns the deliveries this call was responsible for. A channel whose slot
    was already recorded -- by a retry, or by another worker running the same
    tick -- is skipped rather than sent twice.
    """
    deliveries: list[ReminderDelivery] = []

    for channel_name in REMINDER_CHANNELS:
        delivery = _claim_delivery(reminder, scheduled_for, channel_name)
        if delivery is None:
            continue

        _attempt(reminder, delivery, channel_name)
        deliveries.append(delivery)

    return deliveries


def _claim_delivery(
    reminder: Reminder, scheduled_for: Any, channel: str
) -> ReminderDelivery | None:
    """Reserves the slot, or returns None if somebody already holds it.

    The insert is the claim. Checking for an existing row and then creating one
    would leave a window in which two workers both see nothing and both send.
    """
    try:
        with transaction.atomic():
            return ReminderDelivery.objects.create(
                reminder=reminder,
                scheduled_for=scheduled_for,
                channel=channel,
                status=DeliveryStatus.PENDING,
            )
    except IntegrityError:
        return None


def _attempt(reminder: Reminder, delivery: ReminderDelivery, channel_name: str) -> None:
    channel = InAppChannel()
    message = Message(
        recipient=reminder.owner,
        text=reminder_text(reminder),
        idea=reminder.idea,
    )

    try:
        if not channel.is_available_for(reminder.owner):
            raise ChannelUnavailableError(f"کانال {channel_name} در دسترس نیست.")
        channel.send(message)
    except ChannelUnavailableError as error:
        delivery.status = DeliveryStatus.FAILED
        delivery.error = str(error)
        logger.warning(
            "Reminder %s could not be delivered over %s: %s",
            reminder.pk,
            channel_name,
            error,
        )
    else:
        delivery.status = DeliveryStatus.SENT
        delivery.sent_at = timezone.now()

    delivery.save(update_fields=["status", "sent_at", "error", "updated_at"])
