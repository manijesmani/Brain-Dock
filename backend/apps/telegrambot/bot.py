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
from collections.abc import Awaitable, Callable
from typing import Any

from asgiref.sync import async_to_sync
from django.conf import settings
from telegram import Bot, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.request import HTTPXRequest

logger = logging.getLogger(__name__)


class BotNotConfiguredError(RuntimeError):
    """No bot token is set, so nothing can be sent or received."""


def _call[T](operation: Callable[[Bot], Awaitable[T]]) -> T:
    """Runs one exchange with the Bot API on a client that lives only as long.

    `async_to_sync` gives every call from synchronous code a fresh event loop
    and closes it on the way out, while the HTTP client inside a Bot keeps its
    connections open for reuse -- each one bound to the loop that opened it.
    A Bot kept between calls therefore failed every second call with "Event
    loop is closed". Opening the client inside the loop and closing it before
    the loop ends keeps the two lifetimes the same.

    Requests that belong together, such as a file's path and then its bytes,
    go in one operation so they share one loop and one connection.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise BotNotConfiguredError("توکن ربات تلگرام تنظیم نشده است.")

    async def run() -> T:
        # Updates arrive on the webhook, so getUpdates is never called and its
        # slot shares the one client rather than opening a second.
        request = HTTPXRequest()
        bot = Bot(token=token, request=request, get_updates_request=request)
        try:
            return await operation(bot)
        finally:
            await request.shutdown()

    return async_to_sync(run)()


def send_message(
    *,
    chat_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Sends a message, in the limited HTML subset Telegram accepts."""
    _call(
        lambda bot: bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
    )


def answer_callback(*, callback_query_id: str, text: str = "") -> None:
    """Acknowledges a button press.

    Telegram keeps a spinner on the button until this is called, so it runs
    even when the action itself failed.
    """
    try:
        _call(lambda bot: bot.answer_callback_query(callback_query_id=callback_query_id, text=text))
    except TelegramError:
        logger.warning("Could not acknowledge callback %s", callback_query_id)


def edit_message_markup(
    *, chat_id: int, message_id: int, reply_markup: InlineKeyboardMarkup | None
) -> None:
    """Replaces a message's buttons, used to retire them once one is pressed."""
    try:
        _call(
            lambda bot: bot.edit_message_reply_markup(
                chat_id=chat_id, message_id=message_id, reply_markup=reply_markup
            )
        )
    except TelegramError:
        # The message may be too old to edit; the action itself already
        # succeeded, so this is cosmetic.
        logger.debug("Could not edit markup on message %s", message_id)


def download_file(*, file_id: str) -> bytes:
    """Fetches a file the user sent, by the id Telegram gave it."""

    async def download(bot: Bot) -> bytes:
        telegram_file = await bot.get_file(file_id)
        return bytes(await telegram_file.download_as_bytearray())

    return _call(download)


def set_webhook(*, url: str, secret_token: str) -> Any:
    return _call(
        lambda bot: bot.set_webhook(
            url=url,
            secret_token=secret_token,
            # Nothing else is acted on, so nothing else is worth receiving.
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
        )
    )


def delete_webhook() -> Any:
    return _call(lambda bot: bot.delete_webhook(drop_pending_updates=True))


def get_webhook_info() -> Any:
    return _call(lambda bot: bot.get_webhook_info())
