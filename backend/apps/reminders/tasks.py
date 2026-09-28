"""The periodic tick that fires due reminders.

There is exactly one scheduled job in this project. It runs every minute,
reads the reminders whose next firing has arrived, delivers them and computes
the following occurrence.

Nothing is ever queued in advance. A task queued with an `eta` sits in Redis
for however long the delay is: it is lost when the broker restarts, duplicated
when a worker retries, and cannot be cancelled reliably when the user edits or
deletes the rule it belongs to. A row with a `next_run_at` column has none of
those problems -- editing the rule is an UPDATE, and cancelling it is a DELETE.
"""

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.reminders.models import Reminder
from apps.reminders.services import deliver_reminder, refresh_next_run

logger = logging.getLogger(__name__)

# A ceiling on one tick, so a backlog is worked through over several runs
# instead of one task holding a worker indefinitely.
MAX_REMINDERS_PER_TICK = 500


@shared_task(name="reminders.dispatch_due")
def dispatch_due_reminders() -> dict[str, int]:
    """Fires every reminder that has come due."""
    now = timezone.now()

    # An idea in the trash is not reminded of. Its reminder is left as it is,
    # so taking the idea back out brings the reminder back with it.
    due_ids = list(
        Reminder.objects.filter(is_active=True, next_run_at__lte=now, idea__deleted_at__isnull=True)
        .order_by("next_run_at")
        .values_list("id", flat=True)[:MAX_REMINDERS_PER_TICK]
    )

    fired = 0
    skipped = 0

    for reminder_id in due_ids:
        if _process(reminder_id, now):
            fired += 1
        else:
            skipped += 1

    if fired:
        logger.info("Fired %s reminder(s)", fired)

    return {"due": len(due_ids), "fired": fired, "skipped": skipped}


def _process(reminder_id: int, now) -> bool:
    """Handles one reminder inside its own transaction.

    The row is locked for the duration so a second worker running the same
    tick moves on instead of waiting. `skip_locked` is what makes the tick
    safe to run on more than one worker; the unique constraint on delivery is
    what makes it correct even if that guarantee ever fails.
    """
    with transaction.atomic():
        reminder = (
            Reminder.objects.select_for_update(skip_locked=True)
            .select_related("idea", "owner")
            .filter(
                pk=reminder_id,
                is_active=True,
                next_run_at__lte=now,
                idea__deleted_at__isnull=True,
            )
            .first()
        )

        if reminder is None:
            return False

        scheduled_for = reminder.next_run_at

        # The next occurrence is computed from now, not from the slot just
        # fired. After an outage a daily reminder should resume tomorrow, not
        # discharge every missed day at once.
        refresh_next_run(reminder, after=now)
        reminder.save(update_fields=["next_run_at", "is_active", "updated_at"])

        deliver_reminder(reminder=reminder, scheduled_for=scheduled_for)

    return True
