"""What the bot does with an incoming update.

Plain functions rather than a python-telegram-bot Application: an update is
already an HTTP request by the time it reaches Django, so there is nothing an
Application would add except a second lifecycle to manage.

Two shapes arrive. A message either links an account (`/start <token>`) or
becomes an idea. A callback query is one of the reminder buttons.
"""

import logging

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from telegram import Message, Update

from apps.ideas.models import AttachmentKind, IdeaStatus
from apps.ideas.services import create_attachment, create_idea, update_idea
from apps.notifications.models import Notification, NotificationKind
from apps.reminders import services as reminder_services
from apps.reminders.models import Reminder
from apps.telegrambot import bot, messages
from apps.telegrambot.models import TelegramLinkToken
from apps.users.models import User

logger = logging.getLogger(__name__)

# Telegram caps a caption at 1024 characters; a title is shorter still.
TITLE_LIMIT = 200

CAPTURE_TITLES = {
    AttachmentKind.IMAGE: "عکس از تلگرام",
    AttachmentKind.AUDIO: "پیام صوتی از تلگرام",
}


def handle_update(update: Update) -> None:
    """Entry point for one update. Never raises into the webhook."""
    try:
        if update.callback_query is not None:
            _handle_callback(update)
        elif update.message is not None:
            _handle_message(update.message)
    except Exception:
        # A crash here would make Telegram retry the same update forever.
        logger.exception("Failed to handle Telegram update %s", update.update_id)


# --------------------------------------------------------------------------
# Incoming messages
# --------------------------------------------------------------------------


def _handle_message(message: Message) -> None:
    chat_id = message.chat_id
    text = (message.text or "").strip()

    if text.startswith("/start"):
        _handle_start(chat_id, text)
        return

    user = _user_for(chat_id)
    if user is None:
        bot.send_message(chat_id=chat_id, text=messages.NOT_LINKED)
        return

    if message.photo:
        _capture_photo(user, message)
    elif message.voice or message.audio:
        _capture_voice(user, message)
    elif text:
        _capture_text(user, text)
    else:
        bot.send_message(chat_id=chat_id, text=messages.UNSUPPORTED)


def _handle_start(chat_id: int, text: str) -> None:
    """`/start <token>` is how the settings page hands over an account."""
    parts = text.split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else ""

    if not token:
        bot.send_message(chat_id=chat_id, text=messages.WELCOME)
        return

    result = link_account(chat_id=chat_id, token=token)
    bot.send_message(chat_id=chat_id, text=result)


@transaction.atomic
def link_account(*, chat_id: int, token: str) -> str:
    """Binds a chat to the account that issued the token.

    The row is locked while it is checked and spent, so the same link opened
    twice at once cannot connect two chats.
    """
    record = (
        TelegramLinkToken.objects.select_for_update()
        .filter(token=token)
        .select_related("user")
        .first()
    )

    if record is None or not record.is_usable:
        return messages.LINK_INVALID

    # A chat already belonging to someone else must not be re-pointed, or a
    # second person's ideas would start landing in the first one's account.
    taken = User.objects.filter(telegram_chat_id=chat_id).exclude(pk=record.user_id)
    if taken.exists():
        return messages.LINK_TAKEN

    now = timezone.now()

    user = record.user
    user.telegram_chat_id = chat_id
    user.telegram_linked_at = now
    user.save(update_fields=["telegram_chat_id", "telegram_linked_at"])

    record.used_at = now
    record.save(update_fields=["used_at", "updated_at"])

    return messages.LINK_SUCCESS


def _capture_text(user: User, text: str) -> None:
    """The first line becomes the title; the whole message becomes the body."""
    first_line, _, _ = text.partition("\n")
    title = (first_line.strip() or text)[:TITLE_LIMIT]

    idea = create_idea(
        owner=user,
        title=title,
        content=_document(text),
        status=IdeaStatus.IDEA,
    )

    _announce(user, idea)
    bot.send_message(chat_id=user.telegram_chat_id, text=messages.captured_text(idea))


def _capture_photo(user: User, message: Message) -> None:
    # Telegram sends the same photo at several sizes, largest last.
    photo = message.photo[-1]
    caption = (message.caption or "").strip()

    idea = create_idea(
        owner=user,
        title=(caption[:TITLE_LIMIT] or CAPTURE_TITLES[AttachmentKind.IMAGE]),
        content=_document(caption) if caption else None,
        status=IdeaStatus.IDEA,
    )

    _attach(
        idea=idea,
        file_id=photo.file_id,
        filename=f"{photo.file_unique_id}.jpg",
        kind=AttachmentKind.IMAGE,
    )

    _announce(user, idea)
    bot.send_message(chat_id=user.telegram_chat_id, text=messages.captured_text(idea, kind="عکس"))


def _capture_voice(user: User, message: Message) -> None:
    voice = message.voice or message.audio
    caption = (message.caption or "").strip()

    idea = create_idea(
        owner=user,
        title=(caption[:TITLE_LIMIT] or CAPTURE_TITLES[AttachmentKind.AUDIO]),
        content=_document(caption) if caption else None,
        status=IdeaStatus.IDEA,
    )

    _attach(
        idea=idea,
        file_id=voice.file_id,
        filename=f"{voice.file_unique_id}.ogg",
        kind=AttachmentKind.AUDIO,
    )

    _announce(user, idea)
    bot.send_message(
        chat_id=user.telegram_chat_id, text=messages.captured_text(idea, kind="پیام صوتی")
    )


def _attach(*, idea, file_id: str, filename: str, kind: str) -> None:
    """Downloads a file from Telegram and puts it through the normal checks.

    Nothing is trusted because it came from the bot: the same inspectors that
    guard the web upload run here, so a file that is not really an image or
    really audio is rejected the same way.
    """
    payload = bot.download_file(file_id=file_id)
    upload = SimpleUploadedFile(filename, payload)

    create_attachment(idea=idea, upload=upload, kind=kind)


def _document(text: str) -> dict | None:
    """Wraps plain text in the Tiptap shape the editor will open later."""
    if not text.strip():
        return None

    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": line}]}
            if line.strip()
            else {"type": "paragraph"}
            for line in text.split("\n")
        ],
    }


def _announce(user: User, idea) -> None:
    """Mirrors the capture into the notification centre.

    The design's notification list shows exactly this, with the Telegram icon.
    """
    Notification.objects.create(
        owner=user,
        kind=NotificationKind.TELEGRAM_CAPTURE,
        text="یک ایدهٔ جدید از ربات تلگرام ثبت شد",
        idea=idea,
    )


# --------------------------------------------------------------------------
# Button presses
# --------------------------------------------------------------------------


def _handle_callback(update: Update) -> None:
    query = update.callback_query
    data = query.data or ""
    chat_id = query.message.chat_id if query.message else None

    user = _user_for(chat_id) if chat_id is not None else None
    if user is None:
        bot.answer_callback(callback_query_id=query.id, text=messages.NOT_LINKED)
        return

    action, _, raw_id = data.partition(":")
    reminder = (
        Reminder.objects.filter(pk=raw_id, owner=user).select_related("idea").first()
        if raw_id.isdigit()
        else None
    )

    if reminder is None:
        bot.answer_callback(callback_query_id=query.id, text=messages.STALE_ACK)
        return

    acknowledgement = _apply_action(action, reminder)
    bot.answer_callback(callback_query_id=query.id, text=acknowledgement)

    # The buttons are spent once one has been pressed.
    if query.message is not None:
        bot.edit_message_markup(
            chat_id=chat_id, message_id=query.message.message_id, reply_markup=None
        )


def _apply_action(action: str, reminder: Reminder) -> str:
    if action == "done":
        update_idea(idea=reminder.idea, status=IdeaStatus.DONE)
        # A finished idea has nothing left to remind anyone about.
        reminder_services.set_active(reminder=reminder, is_active=False)
        return messages.DONE_ACK

    if action == "snooze":
        reminder_services.snooze(reminder=reminder, minutes=60)
        return messages.SNOOZED_ACK

    if action == "mute":
        reminder_services.set_active(reminder=reminder, is_active=False)
        return messages.MUTED_ACK

    return messages.STALE_ACK


def _user_for(chat_id: int | None) -> User | None:
    if chat_id is None:
        return None
    return User.objects.filter(telegram_chat_id=chat_id).first()
