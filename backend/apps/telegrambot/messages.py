"""Everything the bot says, and the buttons it offers.

Telegram understands only a small subset of HTML -- bold, italic, underline,
strikethrough, code, pre, links and a couple more -- and nothing that nests
the way a rich document does. So messages are built from `plain_text`, the
flattened rendering the server already keeps, never from the Tiptap tree.

Any user-supplied text is escaped before it goes near a tag.
"""

from html import escape

from django.conf import settings
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from apps.ideas.models import Idea
from apps.reminders.messages import describe_schedule
from apps.reminders.models import Reminder

# How much of the body to quote in a reminder before trailing off.
SUMMARY_LIMIT = 240

WELCOME = (
    "سلام! این ربات BrainDock است.\n\n"
    "برای وصل کردن حساب، از صفحهٔ تنظیمات سایت یک لینک اتصال بساز و بازش کن."
)

LINK_SUCCESS = (
    "حسابت وصل شد. ✅\n\n"
    "از این به بعد هر متن، عکس یا پیام صوتی که بفرستی، به‌عنوان یک ایدهٔ تازه "
    "در BrainDock ثبت می‌شود."
)

LINK_INVALID = "این لینک معتبر نیست یا قبلاً استفاده شده.\n\nاز صفحهٔ تنظیمات سایت یک لینک تازه بساز."

LINK_TAKEN = "این حساب تلگرام قبلاً به کاربر دیگری وصل شده است."

NOT_LINKED = "حسابت هنوز وصل نیست.\n\nاز صفحهٔ تنظیمات سایت یک لینک اتصال بساز و بازش کن."

UNSUPPORTED = "فعلاً فقط متن، عکس و پیام صوتی پشتیبانی می‌شود."

CAPTURE_FAILED = "ثبت این پیام ناموفق بود. دوباره امتحان کن."

DONE_ACK = "انجام شد ✅"
SNOOZED_ACK = "یک ساعت دیگر یادآوری می‌کنم"
MUTED_ACK = "یادآوری خاموش شد"
STALE_ACK = "دیگر پیدا نشد"


def idea_url(idea: Idea) -> str:
    return f"{settings.SITE_URL.rstrip('/')}/ideas/{idea.pk}"


def captured_text(idea: Idea, *, kind: str = "ایده") -> str:
    """Confirms a capture and links straight to it."""
    return (
        f"{kind} ثبت شد. ✅\n\n"
        f"<b>{escape(idea.title)}</b>\n\n"
        f'<a href="{idea_url(idea)}">باز کردن در سایت</a>'
    )


def reminder_text(reminder: Reminder) -> str:
    """The reminder itself: title, a little of the body, and the schedule."""
    idea = reminder.idea
    lines = [f"🔔 <b>{escape(idea.title)}</b>"]

    summary = idea.plain_text.strip()
    if summary:
        if len(summary) > SUMMARY_LIMIT:
            summary = summary[:SUMMARY_LIMIT].rstrip() + "…"
        lines.append("")
        lines.append(escape(summary))

    lines.append("")
    lines.append(f"<i>{escape(describe_schedule(reminder))}</i>")

    return "\n".join(lines)


def reminder_keyboard(reminder: Reminder) -> InlineKeyboardMarkup:
    """The four actions the design specifies, two to a row."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("انجام شد", callback_data=f"done:{reminder.pk}"),
                InlineKeyboardButton("یادآوری یک ساعت بعد", callback_data=f"snooze:{reminder.pk}"),
            ],
            [
                InlineKeyboardButton("خاموش کردن یادآوری", callback_data=f"mute:{reminder.pk}"),
                InlineKeyboardButton("باز کردن در سایت", url=idea_url(reminder.idea)),
            ],
        ]
    )


def stale_digest(ideas: list[Idea]) -> str:
    """The summary the phase 7 job sends; the wording lives here with the rest."""
    lines = ["⏳ <b>ایده‌هایی که مدتی است دست‌نخورده مانده‌اند</b>", ""]
    lines.extend(f'• <a href="{idea_url(idea)}">{escape(idea.title)}</a>' for idea in ideas)
    return "\n".join(lines)
