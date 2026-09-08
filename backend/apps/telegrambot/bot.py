"""The Telegram client, and the boundary where async meets Django.

python-telegram-bot is async throughout, while the code that calls it is not:
Django views run synchronously here so the ORM stays straightforward, and the
reminder tick is a Celery task. Rather than making either of those async, the
few Bot API calls are bridged with `async_to_sync`, which is the whole extent
of the asynchrony in this project.

No Application, no updater, no polling loop. Updates arrive as ordinary HTTP
requests on the webhook and are dispatched by plain functions, so there is no
second process to run or supervise.
"""

import logging
from functools import lru_cache
from typing import Any

from asgiref.sync import async_to_sync
from django.conf import settings
from telegram import Bot, InlineKeyboardMarkup
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class BotNotConfiguredError(RuntimeError):
    """No bot token is set, so nothing can be sent or received."""


@lru_cache(maxsize=1)
def get_bot() -> Bot:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise BotNotConfiguredError("توکن ربات تلگرام تنظیم نشده است.")
    return Bot(token=settings.TELEGRAM_BOT_TOKEN)


def send_message(
    *,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Sends a message, in the limited HTML subset Telegram accepts."""
    bot = get_bot()

    async_to_sync(bot.send_message)(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )


def answer_callback(*, callback_query_id: str, text: str = "") -> None:
    """Acknowledges a button press.

    Telegram keeps a spinner on the button until this is called, so it runs
    even when the action itself failed.
    """
    bot = get_bot()

    try:
        async_to_sync(bot.answer_callback_query)(callback_query_id=callback_query_id, text=text)
    except TelegramError:
        logger.warning("Could not acknowledge callback %s", callback_query_id)


def edit_message_markup(
    *, chat_id: int, message_id: int, reply_markup: InlineKeyboardMarkup | None
) -> None:
    """Replaces a message's buttons, used to retire them once one is pressed."""
    bot = get_bot()

    try:
        async_to_sync(bot.edit_message_reply_markup)(
            chat_id=chat_id, message_id=message_id, reply_markup=reply_markup
        )
    except TelegramError:
        # The message may be too old to edit; the action itself already
        # succeeded, so this is cosmetic.
        logger.debug("Could not edit markup on message %s", message_id)


def download_file(*, file_id: str) -> bytes:
    """Fetches a file the user sent, by the id Telegram gave it."""
    bot = get_bot()

    telegram_file = async_to_sync(bot.get_file)(file_id)
    return bytes(async_to_sync(telegram_file.download_as_bytearray)())


def set_webhook(*, url: str, secret_token: str) -> Any:
    bot = get_bot()

    return async_to_sync(bot.set_webhook)(
        url=url,
        secret_token=secret_token,
        # Nothing else is acted on, so nothing else is worth receiving.
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


def delete_webhook() -> Any:
    bot = get_bot()
    return async_to_sync(bot.delete_webhook)(drop_pending_updates=True)


def get_webhook_info() -> Any:
    bot = get_bot()
    return async_to_sync(bot.get_webhook_info)()
