"""Persian presentation helpers.

Everything is stored in UTC and in ASCII digits. These functions are the only
place that converts to the Jalali calendar and Persian numerals, and they run
at the moment of display -- in a notification body, in a Telegram message --
never on the way into the database.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import jdatetime
from django.conf import settings

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

JALALI_MONTHS = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)

# jdatetime numbers weekdays with Saturday at 0, which is also the order the
# design reference uses for its weekday chips.
JALALI_WEEKDAYS = (
    "شنبه",
    "یکشنبه",
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنجشنبه",
    "جمعه",
)


def user_timezone() -> ZoneInfo:
    return ZoneInfo(settings.USER_TIME_ZONE)


def to_persian_digits(value: object) -> str:
    return str(value).translate(PERSIAN_DIGITS)


def to_local(moment: datetime) -> datetime:
    """Converts a stored UTC instant to the user's wall clock."""
    return moment.astimezone(user_timezone())


def format_time(value: time | datetime) -> str:
    """Renders a clock time as Persian digits, e.g. ۹:۰۰."""
    return f"{to_persian_digits(value.hour)}:{to_persian_digits(f'{value.minute:02d}')}"


def format_jalali_date(moment: datetime) -> str:
    """Renders a date as e.g. ۲۳ شهریور ۱۴۰۵."""
    local = to_local(moment)
    jalali = jdatetime.date.fromgregorian(date=local.date())
    day = to_persian_digits(jalali.day)
    year = to_persian_digits(jalali.year)
    return f"{day} {JALALI_MONTHS[jalali.month - 1]} {year}"


def format_jalali_weekday(moment: datetime) -> str:
    local = to_local(moment)
    jalali = jdatetime.date.fromgregorian(date=local.date())
    return JALALI_WEEKDAYS[jalali.weekday()]


def format_jalali_datetime(moment: datetime) -> str:
    """Renders a full instant, e.g. ۲۳ شهریور ۱۴۰۵، ساعت ۹:۰۰."""
    local = to_local(moment)
    return f"{format_jalali_date(moment)}، ساعت {format_time(local)}"
