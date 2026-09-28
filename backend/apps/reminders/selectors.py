"""Read paths for reminders."""

from datetime import UTC, datetime, time, timedelta

from django.db.models import QuerySet
from django.utils import timezone

from apps.reminders.models import Reminder
from apps.reminders.recurrence import compute_next_run
from apps.users.models import User
from core.formatting import user_timezone


def reminder_queryset(*, owner: User) -> QuerySet[Reminder]:
    return Reminder.objects.filter(owner=owner, idea__deleted_at__isnull=True).select_related(
        "idea", "idea__category", "owner"
    )


def _start_of_today() -> datetime:
    """Midnight tonight on the user's clock, as a UTC instant."""
    local = timezone.now().astimezone(user_timezone())
    return datetime.combine(local.date(), time.min).replace(tzinfo=user_timezone()).astimezone(UTC)


def due_today(reminders: list[Reminder]) -> list[Reminder]:
    """Reminders with a slot somewhere in today, passed or still ahead.

    The dashboard's first section is the day's agenda, not what is left of it,
    so a daily reminder at 09:00 still belongs there at noon. Each rule is
    evaluated from the start of today rather than from now, which is what makes
    an already-delivered slot count.
    """
    start = _start_of_today()
    end = start + timedelta(days=1)

    return [
        reminder
        for reminder in reminders
        if _first_occurrence_from(reminder, start) is not None
        and _first_occurrence_from(reminder, start) < end
    ]


def due_this_week(reminders: list[Reminder]) -> list[Reminder]:
    """Reminders firing in the next seven days, excluding today's agenda."""
    now = timezone.now()
    horizon = now + timedelta(days=7)
    today = {reminder.pk for reminder in due_today(reminders)}

    return [
        reminder
        for reminder in reminders
        if reminder.pk not in today
        and reminder.next_run_at is not None
        and now <= reminder.next_run_at <= horizon
    ]


def _first_occurrence_from(reminder: Reminder, moment: datetime) -> datetime | None:
    # `compute_next_run` answers strictly after its reference, so a slot at
    # exactly midnight is not lost.
    return compute_next_run(reminder.schedule, after=moment - timedelta(microseconds=1))
