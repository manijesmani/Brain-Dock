"""Delivery over the Telegram bot.

Unavailable for anyone who has not linked their account, and for everyone if
no bot token is configured. The reminder engine already treats an unavailable
channel as a failed delivery for that channel alone, so an unlinked user still
gets the in-app notification.
"""

import logging

from apps.notifications.channels.base import ChannelUnavailableError, Message
from apps.telegrambot import bot, messages
from apps.telegrambot.bot import BotNotConfiguredError
from apps.users.models import User

logger = logging.getLogger(__name__)


class TelegramChannel:
    name = "telegram"

    def is_available_for(self, user: User) -> bool:
        return user.is_telegram_linked

    def send(self, message: Message) -> None:
        chat_id = message.recipient.telegram_chat_id
        if chat_id is None:
            raise ChannelUnavailableError("حساب تلگرام این کاربر وصل نیست.")

        try:
            bot.send_message(
                chat_id=chat_id,
                text=message.text,
                reply_markup=message.reply_markup,
            )
        except BotNotConfiguredError as error:
            raise ChannelUnavailableError(str(error)) from error
        except Exception as error:
            # A Telegram outage must not stop the tick or lose the slot; the
            # delivery is recorded as failed and the next one is attempted.
            raise ChannelUnavailableError(f"ارسال تلگرام ناموفق بود: {error}") from error


def reminder_message(reminder) -> tuple[str, object]:
    """The reminder body and its buttons, built from `plain_text`.

    Telegram understands only a narrow subset of HTML, so the flattened text
    is what gets sent -- never the Tiptap document.
    """
    return messages.reminder_text(reminder), messages.reminder_keyboard(reminder)
