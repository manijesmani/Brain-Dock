"""The next-run calculator.

These tests need no database. They are the ones to read first when the
reminder engine misbehaves, because every scheduling bug shows up here before
it shows up anywhere else.
"""

from datetime import UTC, datetime

import jdatetime
import pytest

from apps.reminders.recurrence import (
    Schedule,
    compute_next_run,
    days_in_jalali_month,
    is_jalali_leap_year,
    jalali_weekday,
)
from core.formatting import user_timezone


def tehran(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """An instant given in the Jalali calendar and Tehran wall time."""
    naive = jdatetime.datetime(year, month, day, hour, minute).togregorian()
    return naive.replace(tzinfo=user_timezone()).astimezone(UTC)


def as_jalali(moment: datetime) -> tuple[int, int, int, int, int]:
    local = moment.astimezone(user_timezone())
    jalali = jdatetime.date.fromgregorian(date=local.date())
    return (jalali.year, jalali.month, jalali.day, local.hour, local.minute)


class TestJalaliCalendar:
    @pytest.mark.parametrize(
        ("year", "expected"),
        [(1403, True), (1404, False), (1405, False), (1408, True)],
    )
    def test_leap_years(self, year: int, expected: bool) -> None:
        assert is_jalali_leap_year(year) is expected

    def test_month_lengths_in_an_ordinary_year(self) -> None:
        lengths = [days_in_jalali_month(1405, month) for month in range(1, 13)]

        assert lengths == [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]

    def test_esfand_gains_a_day_in_a_leap_year(self) -> None:
        assert days_in_jalali_month(1403, 12) == 30
        assert days_in_jalali_month(1404, 12) == 29

    def test_saturday_is_weekday_zero(self) -> None:
        """The design's weekday chips start at Saturday, and so does this."""
        saturday = jdatetime.date(1405, 6, 21).togregorian()

        assert saturday.strftime("%A") == "Saturday"
        assert jalali_weekday(saturday) == 0


class TestDaily:
    def test_later_today_when_the_time_has_not_passed(self) -> None:
        result = compute_next_run(Schedule("daily", 18, 0), after=tehran(1405, 6, 23, 10, 30))

        assert as_jalali(result) == (1405, 6, 23, 18, 0)

    def test_tomorrow_when_the_time_has_passed(self) -> None:
        result = compute_next_run(Schedule("daily", 9, 0), after=tehran(1405, 6, 23, 10, 30))

        assert as_jalali(result) == (1405, 6, 24, 9, 0)

    def test_the_exact_minute_counts_as_passed(self) -> None:
        """A firing is scheduled strictly after the reference, so the slot
        just delivered is never selected again."""
        result = compute_next_run(Schedule("daily", 9, 0), after=tehran(1405, 6, 23, 9, 0))

        assert as_jalali(result) == (1405, 6, 24, 9, 0)

    def test_the_result_is_stored_in_utc(self) -> None:
        result = compute_next_run(Schedule("daily", 9, 0), after=tehran(1405, 6, 23, 0, 0))

        # Tehran is UTC+03:30, so 09:00 local is 05:30 UTC.
        assert result.tzinfo == UTC
        assert (result.hour, result.minute) == (5, 30)

    def test_crossing_the_gregorian_year_boundary(self) -> None:
        """Dey 11 is 1 January; the Jalali year does not turn there."""
        result = compute_next_run(Schedule("daily", 9, 0), after=tehran(1405, 10, 10, 23, 0))

        assert as_jalali(result) == (1405, 10, 11, 9, 0)


class TestWeekly:
    def test_the_next_matching_weekday(self) -> None:
        # 23 Shahrivar 1405 is a Monday, which is index 2.
        result = compute_next_run(
            Schedule("weekly", 9, 0, weekdays=(6,)), after=tehran(1405, 6, 23, 10, 30)
        )

        assert as_jalali(result) == (1405, 6, 27, 9, 0)
        assert jalali_weekday(result.astimezone(user_timezone()).date()) == 6

    def test_today_still_counts_if_the_time_has_not_passed(self) -> None:
        result = compute_next_run(
            Schedule("weekly", 18, 0, weekdays=(2,)), after=tehran(1405, 6, 23, 10, 30)
        )

        assert as_jalali(result) == (1405, 6, 23, 18, 0)

    def test_the_soonest_of_several_days_wins(self) -> None:
        result = compute_next_run(
            Schedule("weekly", 9, 0, weekdays=(0, 3, 6)),
            after=tehran(1405, 6, 23, 10, 30),
        )

        # Tuesday (index 3) is the day after Monday.
        assert as_jalali(result) == (1405, 6, 24, 9, 0)

    def test_a_week_later_when_today_is_the_only_day_and_it_has_passed(self) -> None:
        result = compute_next_run(
            Schedule("weekly", 9, 0, weekdays=(2,)), after=tehran(1405, 6, 23, 10, 30)
        )

        assert as_jalali(result) == (1405, 6, 30, 9, 0)

    def test_no_weekdays_means_no_next_run(self) -> None:
        assert compute_next_run(Schedule("weekly", 9, 0), after=tehran(1405, 6, 23)) is None


class TestMonthly:
    """The case the whole engine exists to get right.

    Jalali months are 31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, and then 29
    or 30. A day that does not exist in a given month has to fall back to that
    month's last day rather than being skipped.
    """

    def test_the_same_month_when_the_day_is_still_ahead(self) -> None:
        result = compute_next_run(
            Schedule("monthly", 9, 0, day_of_month=25),
            after=tehran(1405, 6, 23, 10, 30),
        )

        assert as_jalali(result) == (1405, 6, 25, 9, 0)

    def test_the_next_month_when_the_day_has_passed(self) -> None:
        result = compute_next_run(
            Schedule("monthly", 9, 0, day_of_month=10),
            after=tehran(1405, 6, 23, 10, 30),
        )

        assert as_jalali(result) == (1405, 7, 10, 9, 0)

    def test_day_31_falls_to_day_30_in_a_thirty_day_month(self) -> None:
        # Mehr is the seventh month and has 30 days.
        result = compute_next_run(
            Schedule("monthly", 9, 0, day_of_month=31), after=tehran(1405, 7, 1)
        )

        assert as_jalali(result) == (1405, 7, 30, 9, 0)

    def test_day_31_falls_to_day_29_in_an_ordinary_esfand(self) -> None:
        result = compute_next_run(
            Schedule("monthly", 9, 0, day_of_month=31), after=tehran(1405, 12, 1)
        )

        assert as_jalali(result) == (1405, 12, 29, 9, 0)

    def test_day_31_falls_to_day_30_in_a_leap_esfand(self) -> None:
        result = compute_next_run(
            Schedule("monthly", 9, 0, day_of_month=31), after=tehran(1403, 12, 1)
        )

        assert as_jalali(result) == (1403, 12, 30, 9, 0)

    def test_day_30_is_reached_in_a_leap_esfand_but_clamped_otherwise(self) -> None:
        leap = compute_next_run(
            Schedule("monthly", 9, 0, day_of_month=30), after=tehran(1403, 12, 1)
        )
        ordinary = compute_next_run(
            Schedule("monthly", 9, 0, day_of_month=30), after=tehran(1404, 12, 1)
        )

        assert as_jalali(leap)[:3] == (1403, 12, 30)
        assert as_jalali(ordinary)[:3] == (1404, 12, 29)

    def test_a_full_year_of_the_thirty_first(self) -> None:
        """Every month fires, none is skipped, and each lands on its own last
        day when it is too short."""
        schedule = Schedule("monthly", 9, 0, day_of_month=31)
        cursor = tehran(1405, 1, 1)
        fired = []

        for _ in range(12):
            cursor = compute_next_run(schedule, after=cursor)
            _year, month, day, *_ = as_jalali(cursor)
            fired.append((month, day))

        assert fired == [
            (1, 31),
            (2, 31),
            (3, 31),
            (4, 31),
            (5, 31),
            (6, 31),
            (7, 30),
            (8, 30),
            (9, 30),
            (10, 30),
            (11, 30),
            (12, 29),
        ]

    def test_rolling_from_esfand_into_the_new_year(self) -> None:
        result = compute_next_run(
            Schedule("monthly", 9, 0, day_of_month=5), after=tehran(1405, 12, 20)
        )

        assert as_jalali(result) == (1406, 1, 5, 9, 0)

    def test_no_day_of_month_means_no_next_run(self) -> None:
        assert compute_next_run(Schedule("monthly", 9, 0), after=tehran(1405, 6, 23)) is None


class TestExact:
    def test_a_future_moment_is_returned(self) -> None:
        from datetime import date

        result = compute_next_run(
            Schedule("exact", 9, 0, exact_date=jdatetime.date(1405, 6, 25).togregorian()),
            after=tehran(1405, 6, 23, 10, 30),
        )

        assert isinstance(result, datetime)
        assert as_jalali(result) == (1405, 6, 25, 9, 0)
        assert isinstance(jdatetime.date(1405, 6, 25).togregorian(), date)

    def test_a_past_moment_returns_none(self) -> None:
        """Which is how the caller knows to deactivate a spent one-off."""
        result = compute_next_run(
            Schedule("exact", 9, 0, exact_date=jdatetime.date(1405, 6, 20).togregorian()),
            after=tehran(1405, 6, 23, 10, 30),
        )

        assert result is None

    def test_today_before_the_time_still_fires(self) -> None:
        result = compute_next_run(
            Schedule("exact", 18, 0, exact_date=jdatetime.date(1405, 6, 23).togregorian()),
            after=tehran(1405, 6, 23, 10, 30),
        )

        assert as_jalali(result) == (1405, 6, 23, 18, 0)


class TestUnknownKind:
    def test_it_raises_rather_than_silently_returning_none(self) -> None:
        with pytest.raises(ValueError, match="Unknown recurrence kind"):
            compute_next_run(Schedule("yearly", 9, 0), after=tehran(1405, 6, 23))
