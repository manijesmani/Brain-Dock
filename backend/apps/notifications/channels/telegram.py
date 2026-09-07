"""Delivery over the Telegram bot.

The bot itself arrives in phase 6. Until then this channel reports itself as
unavailable for every user, which is the same answer it will give afterwards
for anyone who has not linked their account -- so the reminder engine already
handles the case correctly and needs no change when the bot lands.
"""

from apps.notifications.channels.base import ChannelUnavailableError, Message
from apps.users.models import User


class TelegramChannel:
    name = "telegram"

    def is_available_for(self, user: User) -> bool:
        # Linking exists on the model from phase 0, but nothing sets it yet.
        return user.is_telegram_linked

    def send(self, message: Message) -> None:
        raise ChannelUnavailableError("ربات تلگرام هنوز راه‌اندازی نشده است.")
