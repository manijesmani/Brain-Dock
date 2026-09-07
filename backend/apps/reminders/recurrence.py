"""Computing when a reminder fires next.

This is the one piece of arithmetic the whole feature rests on, and it has two
properties that make it easy to get wrong.

The first is the calendar. Monthly recurrence has to be resolved in the Jalali
calendar, not the Gregorian one: Jalali months run 31, 31, 31, 31, 31, 31, 30,
30, 30, 30, 30, and then 29 or 30 in a leap year, and their boundaries do not
line up with Gregorian months at all. "The 31st of every month" therefore
lands on the last day of any month that is shorter, which is most of them.

The second is the time zone. Every instant is stored in UTC, but a reminder is
expressed in the user's wall clock -- "every day at 09:00" means 09:00 in
Tehran. So each candidate is built as a naive local time and only then
converted, rather than doing arithmetic on UTC and hoping the offset holds.

Weekdays are numbered with Saturday at 0, matching both jdatetime and the
weekday chips in the design reference.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

import jdatetime

from core.formatting import user_timezone

# How far ahead the monthly search is willing to look. A whole year plus a
# margin: any valid day-of-month occurs within twelve months, so exceeding
# this means the inputs were impossible rather than merely distant.
MAX_MONTH_LOOKAHEAD = 14

SATURDAY_INDEX = 0
DAYS_IN_WEEK = 7

RecurrenceKind = Literal["daily", "weekly", "monthly", "exact"]


@dataclass(frozen=True)
class Schedule:
    """The recurrence rule, independent of any model."""

    kind: RecurrenceKind
    hour: int
    minute: int
    weekdays: tuple[int, ...] = ()
    day_of_month: int | None = None
    exact_date: date | None = None


def is_jalali_leap_year(year: int) -> bool:
    return jdatetime.date(year, 1, 1).isleap()


def days_in_jalali_month(year: int, month: int) -> int:
    """Length of a Jalali month: 31 for the first six, 30 for the next five,
    and 29 or 30 for Esfand depending on the leap year."""
    if month <= 6:
        return 31
    if month <= 11:
        return 30
    return 30 if is_jalali_leap_year(year) else 29


def jalali_weekday(value: date) -> int:
    """Weekday index with Saturday at 0."""
    return jdatetime.date.fromgregorian(date=value).weekday()


def _to_local_naive(moment: datetime) -> datetime:
    return moment.astimezone(user_timezone()).replace(tzinfo=None)


def _to_utc(local_naive: datetime) -> datetime:
    from datetime import UTC

    return local_naive.replace(tzinfo=user_timezone()).astimezone(UTC)


def _at(day: date, hour: int, minute: int) -> datetime:
    return datetime.combine(day, time(hour=hour, minute=minute))


def compute_next_run(schedule: Schedule, *, after: datetime) -> datetime | None:
    """The first firing strictly after `after`, or None if there is none.

    `after` is an aware instant; the result is an aware UTC instant. A
    non-repeating reminder whose moment has passed returns None, which is how
    the caller knows to deactivate it.
    """
    local_after = _to_local_naive(after)

    if schedule.kind == "daily":
        return _next_daily(schedule, local_after)
    if schedule.kind == "weekly":
        return _next_weekly(schedule, local_after)
    if schedule.kind == "monthly":
        return _next_monthly(schedule, local_after)
    if schedule.kind == "exact":
        return _next_exact(schedule, local_after)

    raise ValueError(f"Unknown recurrence kind: {schedule.kind}")


def _next_daily(schedule: Schedule, local_after: datetime) -> datetime:
    candidate = _at(local_after.date(), schedule.hour, schedule.minute)
    if candidate <= local_after:
        candidate = _at(local_after.date() + timedelta(days=1), schedule.hour, schedule.minute)
    return _to_utc(candidate)


def _next_weekly(schedule: Schedule, local_after: datetime) -> datetime | None:
    if not schedule.weekdays:
        return None

    wanted = set(schedule.weekdays)

    # Today plus a full week: the first hit is the answer, and a rule with at
    # least one weekday always hits within seven days.
    for offset in range(DAYS_IN_WEEK + 1):
        day = local_after.date() + timedelta(days=offset)
        if jalali_weekday(day) not in wanted:
            continue
        candidate = _at(day, schedule.hour, schedule.minute)
        if candidate > local_after:
            return _to_utc(candidate)

    return None


def _next_monthly(schedule: Schedule, local_after: datetime) -> datetime | None:
    if schedule.day_of_month is None:
        return None

    jalali_today = jdatetime.date.fromgregorian(date=local_after.date())
    year, month = jalali_today.year, jalali_today.month

    for _ in range(MAX_MONTH_LOOKAHEAD):
        # A day that does not exist this month falls back to the last one, so
        # "the 31st" still fires in a 30-day month rather than being skipped.
        day = min(schedule.day_of_month, days_in_jalali_month(year, month))
        gregorian = jdatetime.date(year, month, day).togregorian()

        candidate = _at(gregorian, schedule.hour, schedule.minute)
        if candidate > local_after:
            return _to_utc(candidate)

        year, month = (year + 1, 1) if month == 12 else (year, month + 1)

    return None


def _next_exact(schedule: Schedule, local_after: datetime) -> datetime | None:
    if schedule.exact_date is None:
        return None

    candidate = _at(schedule.exact_date, schedule.hour, schedule.minute)
    if candidate <= local_after:
        return None

    return _to_utc(candidate)
