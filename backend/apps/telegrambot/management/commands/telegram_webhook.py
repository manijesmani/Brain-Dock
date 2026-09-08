"""Registers, inspects or removes the bot's webhook.

Telegram has to be told once where to deliver updates. Doing that from a
command rather than at start-up keeps deployment explicit: nothing reaches out
to Telegram just because a process booted.
"""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.telegrambot import bot
from apps.telegrambot.bot import BotNotConfiguredError

WEBHOOK_PATH = "/api/telegram/webhook/"


class Command(BaseCommand):
    help = "Sets, shows or deletes the Telegram webhook."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "action",
            choices=["set", "info", "delete"],
            help="set registers the webhook, info reports it, delete removes it",
        )
        parser.add_argument(
            "--base-url",
            help="Public HTTPS base address; defaults to SITE_URL.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            if options["action"] == "set":
                self._set(options.get("base_url"))
            elif options["action"] == "info":
                self._info()
            else:
                self._delete()
        except BotNotConfiguredError as error:
            raise CommandError(str(error)) from error

    def _set(self, base_url: str | None) -> None:
        if not settings.TELEGRAM_WEBHOOK_SECRET:
            raise CommandError(
                "TELEGRAM_WEBHOOK_SECRET is not set. Without it the webhook refuses every update."
            )

        base = (base_url or settings.SITE_URL).rstrip("/")
        if not base.startswith("https://"):
            # Telegram will not deliver to a plain-text endpoint.
            raise CommandError(f"The webhook must be HTTPS; got {base}")

        url = f"{base}{WEBHOOK_PATH}"
        bot.set_webhook(url=url, secret_token=settings.TELEGRAM_WEBHOOK_SECRET)
        self.stdout.write(self.style.SUCCESS(f"Webhook set to {url}"))

    def _info(self) -> None:
        info = bot.get_webhook_info()
        self.stdout.write(f"url: {info.url or '(none)'}")
        self.stdout.write(f"pending updates: {info.pending_update_count}")
        if info.last_error_message:
            self.stdout.write(self.style.WARNING(f"last error: {info.last_error_message}"))

    def _delete(self) -> None:
        bot.delete_webhook()
        self.stdout.write(self.style.SUCCESS("Webhook removed"))
