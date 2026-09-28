"""The Telegram client itself, against a stand-in Bot API on localhost.

The rest of the suite replaces `apps.telegrambot.bot` with a recorder. These
tests keep the real client -- python-telegram-bot, httpx and the
`async_to_sync` bridge -- and fake only the far end: a local HTTP server that
answers the way api.telegram.org does, keep-alive included.

Keep-alive is the point. A client kept between calls held on to a pooled
connection bound to the event loop of the call that opened it, and the next
call, running on a new loop, failed with "Event loop is closed".
"""

import json
import threading
from collections.abc import Iterator
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from telegram import Bot

from apps.ideas.models import Attachment, AttachmentKind, Idea
from apps.telegrambot import bot
from apps.users.models import User
from tests.media_fixtures import image_bytes

CHAT_ID = 987654321
SECRET = "webhook-secret"
PHOTO = image_bytes(size=(200, 150))

MESSAGE = {"message_id": 1, "date": 0, "chat": {"id": CHAT_ID, "type": "private"}}

# What each Bot API method answers with. Only `result` matters to the client.
RESULTS = {
    "sendMessage": MESSAGE,
    "answerCallbackQuery": True,
    "editMessageReplyMarkup": MESSAGE,
    "getFile": {"file_id": "photo-1", "file_unique_id": "uniq-1", "file_path": "photos/1.jpg"},
}


class FakeBotAPI(BaseHTTPRequestHandler):
    # HTTP/1.1 keeps connections open between requests, as Telegram does.
    protocol_version = "HTTP/1.1"

    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        method = self.path.rsplit("/", 1)[-1]
        self.server.calls.append(method)
        self._reply(json.dumps({"ok": True, "result": RESULTS[method]}).encode())

    def do_GET(self) -> None:
        # File downloads are the only GETs the client makes.
        self.server.calls.append("download")
        self._reply(PHOTO)

    def _reply(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def calls(settings, monkeypatch) -> Iterator[list[str]]:
    """Points the client at a local Bot API and yields the methods it receives."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeBotAPI)
    server.calls = []
    threading.Thread(target=server.serve_forever, daemon=True).start()

    base = f"http://127.0.0.1:{server.server_address[1]}"
    settings.TELEGRAM_BOT_TOKEN = "123456:test-token"
    monkeypatch.setattr(
        bot, "Bot", partial(Bot, base_url=f"{base}/bot", base_file_url=f"{base}/file/bot")
    )

    yield server.calls

    server.shutdown()
    server.server_close()


class TestClient:
    def test_consecutive_calls_all_reach_the_api(self, calls: list[str]) -> None:
        """The second of these is the one that used to fail."""
        for _ in range(3):
            bot.send_message(chat_id=CHAT_ID, text="سلام")

        assert calls == ["sendMessage"] * 3

    def test_a_file_is_located_then_downloaded(self, calls: list[str]) -> None:
        assert bot.download_file(file_id="photo-1") == PHOTO
        assert calls == ["getFile", "download"]

    def test_a_button_press_is_acknowledged_and_its_buttons_retired(self, calls: list[str]) -> None:
        bot.answer_callback(callback_query_id="cbq-1", text="انجام شد")
        bot.edit_message_markup(chat_id=CHAT_ID, message_id=1, reply_markup=None)

        assert calls == ["answerCallbackQuery", "editMessageReplyMarkup"]

    def test_nothing_is_attempted_without_a_token(self, calls: list[str], settings) -> None:
        settings.TELEGRAM_BOT_TOKEN = ""

        with pytest.raises(bot.BotNotConfiguredError):
            bot.send_message(chat_id=CHAT_ID, text="سلام")

        assert calls == []


@pytest.mark.django_db
def test_a_photo_sent_to_the_bot_is_stored_and_answered(
    calls: list[str], settings, api_client: APIClient, user: User
) -> None:
    """The whole path production takes: webhook, handler, client and back."""
    settings.TELEGRAM_WEBHOOK_SECRET = SECRET
    # The bot serves the site's owner alone.
    user.is_superuser = True
    user.telegram_chat_id = CHAT_ID
    user.save(update_fields=["is_superuser", "telegram_chat_id"])

    update = {
        "update_id": 1,
        "message": {
            **MESSAGE,
            "caption": "ایده‌ای از تلگرام",
            "photo": [
                {"file_id": "photo-1", "file_unique_id": "uniq-1", "width": 200, "height": 150}
            ],
        },
    }

    response = api_client.post(
        reverse("telegrambot:webhook"),
        update,
        format="json",
        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=SECRET,
    )

    assert response.status_code == 200
    idea = Idea.objects.get(owner=user)
    assert idea.title == "ایده‌ای از تلگرام"
    assert Attachment.objects.get(idea=idea).kind == AttachmentKind.IMAGE
    assert calls == ["getFile", "download", "sendMessage"]
