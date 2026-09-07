"""Wording of reminder notifications.

Kept apart from the dispatch logic so the Persian text lives in one place and
can be read without wading through scheduling code.
"""

from datetime import time

from apps.reminders.models import Reminder, ReminderRecurrence
from core.formatting import format_jalali_date, format_time

RECURRENCE_PHRASES = {
    ReminderRecurrence.DAILY: "هر روز",
    ReminderRecurrence.WEEKLY: "هفتگی",
    ReminderRecurrence.MONTHLY: "ماهانه",
}


def describe_schedule(reminder: Reminder) -> str:
    """A short rendering of the rule, e.g. «هر روز ساعت ۹:۰۰»."""
    clock = f"ساعت {format_time(time(hour=reminder.hour, minute=reminder.minute))}"

    phrase = RECURRENCE_PHRASES.get(reminder.recurrence)
    if phrase is not None:
        return f"{phrase} {clock}"

    # A one-off reminder names its date instead of a repetition.
    if reminder.next_run_at is not None:
        return f"{format_jalali_date(reminder.next_run_at)}، {clock}"

    return clock


def reminder_text(reminder: Reminder) -> str:
    """The notification body, e.g. «یادآوری: سری استوری، هر روز ساعت ۹:۰۰»."""
    return f"یادآوری: {reminder.idea.title}، {describe_schedule(reminder)}"
