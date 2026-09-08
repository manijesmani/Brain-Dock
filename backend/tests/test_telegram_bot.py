"""The Telegram bot: capture in, reminders out.

Nothing here touches Telegram. `bot` is replaced by a recorder, so the tests
assert on what would have been sent rather than on a network call, and the
handlers run exactly as they do in production.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ideas.models import Attachment, AttachmentKind, Idea, IdeaStatus
from apps.notifications.models import Notification, NotificationKind
from apps.reminders import services as reminder_services
from apps.reminders.models import DeliveryChannel, DeliveryStatus, ReminderRecurrence
from apps.telegrambot import handlers, messages
from apps.telegrambot.models import TelegramLinkToken
from apps.users.models import User
from tests.factories import IdeaFactory
from tests.media_fixtures import image_bytes

pytestmark = pytest.mark.django_db

CHAT_ID = 987654321


@dataclass
class SentMessage:
    chat_id: int
    text: str
    reply_markup: Any = None


@dataclass
class BotRecorder:
    """Stands in for the Telegram client and remembers what it was asked to do."""

    sent: list[SentMessage] = field(default_factory=list)
    answered: list[str] = field(default_factory=list)
    edited: list[int] = field(default_factory=list)
    files: dict[str, bytes] = field(default_factory=dict)

    def send_message(self, *, chat_id, text, reply_markup=None):
        self.sent.append(SentMessage(chat_id, text, reply_markup))

    def answer_callback(self, *, callback_query_id, text=""):
        self.answered.append(text)

    def edit_message_markup(self, *, chat_id, message_id, reply_markup):
        self.edited.append(message_id)

    def download_file(self, *, file_id):
        return self.files.get(file_id, image_bytes(size=(200, 150)))


@pytest.fixture
def recorder(monkeypatch) -> BotRecorder:
    recording = BotRecorder()
    for module in ("apps.telegrambot.handlers", "apps.notifications.channels.telegram"):
        monkeypatch.setattr(f"{module}.bot", recording, raising=False)
    return recording


@pytest.fixture
def linked_user(user: User) -> User:
    user.telegram_chat_id = CHAT_ID
    user.telegram_linked_at = timezone.now()
    user.save(update_fields=["telegram_chat_id", "telegram_linked_at"])
    return user


# --------------------------------------------------------------------------
# Fake updates, shaped the way python-telegram-bot presents them
# --------------------------------------------------------------------------


class FakeChat:
    def __init__(self, chat_id: int) -> None:
        self.id = chat_id


class FakeMessage:
    def __init__(self, chat_id=CHAT_ID, text=None, caption=None, photo=None, voice=None):
        self.chat_id = chat_id
        self.chat = FakeChat(chat_id)
        self.text = text
        self.caption = caption
        self.photo = photo or []
        self.voice = voice
        self.audio = None
        self.message_id = 42


class FakePhotoSize:
    def __init__(self, file_id="photo-1", unique="uniq-1"):
        self.file_id = file_id
        self.file_unique_id = unique


class FakeVoice:
    def __init__(self, file_id="voice-1", unique="uniq-2"):
        self.file_id = file_id
        self.file_unique_id = unique


class FakeCallbackQuery:
    def __init__(self, data, chat_id=CHAT_ID):
        self.id = "cbq-1"
        self.data = data
        self.message = FakeMessage(chat_id=chat_id)


class FakeUpdate:
    def __init__(self, message=None, callback_query=None):
        self.update_id = 1
        self.message = message
        self.callback_query = callback_query


# --------------------------------------------------------------------------


class TestAccountLinking:
    def test_a_valid_token_links_the_chat(self, recorder, user: User) -> None:
        token = TelegramLinkToken.objects.create(
            user=user, expires_at=timezone.now() + timedelta(minutes=10)
        )

        handlers.handle_update(FakeUpdate(FakeMessage(text=f"/start {token.token}")))

        user.refresh_from_db()
        token.refresh_from_db()
        assert user.telegram_chat_id == CHAT_ID
        assert user.telegram_linked_at is not None
        assert token.used_at is not None
        assert recorder.sent[-1].text == messages.LINK_SUCCESS

    def test_a_token_cannot_be_spent_twice(self, recorder, user: User) -> None:
        token = TelegramLinkToken.objects.create(
            user=user, expires_at=timezone.now() + timedelta(minutes=10)
        )
        handlers.handle_update(FakeUpdate(FakeMessage(text=f"/start {token.token}")))

        handlers.handle_update(FakeUpdate(FakeMessage(text=f"/start {token.token}")))

        assert recorder.sent[-1].text == messages.LINK_INVALID

    def test_an_expired_token_is_refused(self, recorder, user: User) -> None:
        token = TelegramLinkToken.objects.create(
            user=user, expires_at=timezone.now() - timedelta(seconds=1)
        )

        handlers.handle_update(FakeUpdate(FakeMessage(text=f"/start {token.token}")))

        user.refresh_from_db()
        assert user.telegram_chat_id is None
        assert recorder.sent[-1].text == messages.LINK_INVALID

    def test_an_unknown_token_is_refused(self, recorder, user: User) -> None:
        handlers.handle_update(FakeUpdate(FakeMessage(text="/start not-a-real-token")))

        assert recorder.sent[-1].text == messages.LINK_INVALID

    def test_a_chat_already_linked_elsewhere_is_refused(
        self, recorder, linked_user: User, other_user: User
    ) -> None:
        """Otherwise a second person's ideas would land in the first's account."""
        token = TelegramLinkToken.objects.create(
            user=other_user, expires_at=timezone.now() + timedelta(minutes=10)
        )

        handlers.handle_update(FakeUpdate(FakeMessage(text=f"/start {token.token}")))

        other_user.refresh_from_db()
        assert other_user.telegram_chat_id is None
        assert recorder.sent[-1].text == messages.LINK_TAKEN

    def test_bare_start_explains_how_to_link(self, recorder, user: User) -> None:
        handlers.handle_update(FakeUpdate(FakeMessage(text="/start")))

        assert recorder.sent[-1].text == messages.WELCOME

    def test_an_unlinked_chat_is_told_to_link(self, recorder) -> None:
        handlers.handle_update(FakeUpdate(FakeMessage(text="یک ایدهٔ تازه")))

        assert Idea.objects.count() == 0
        assert recorder.sent[-1].text == messages.NOT_LINKED


class TestCapture:
    def test_text_becomes_an_idea(self, recorder, linked_user: User) -> None:
        handlers.handle_update(FakeUpdate(FakeMessage(text="ایدهٔ ضبط پادکست هفتگی")))

        idea = Idea.objects.get()
        assert idea.owner == linked_user
        assert idea.title == "ایدهٔ ضبط پادکست هفتگی"
        assert idea.status == IdeaStatus.IDEA
        assert "پادکست" in idea.plain_text

    def test_a_multiline_message_uses_its_first_line_as_the_title(
        self, recorder, linked_user: User
    ) -> None:
        handlers.handle_update(
            FakeUpdate(FakeMessage(text="سری استوری\nهر روز یک ترفند کوچک از ادیتور."))
        )

        idea = Idea.objects.get()
        assert idea.title == "سری استوری"
        assert "ترفند" in idea.plain_text

    def test_a_capture_is_mirrored_into_the_notification_centre(
        self, recorder, linked_user: User
    ) -> None:
        handlers.handle_update(FakeUpdate(FakeMessage(text="ایده")))

        notification = Notification.objects.get()
        assert notification.kind == NotificationKind.TELEGRAM_CAPTURE
        assert notification.text == "یک ایدهٔ جدید از ربات تلگرام ثبت شد"

    def test_the_confirmation_links_back_to_the_idea(self, recorder, linked_user: User) -> None:
        handlers.handle_update(FakeUpdate(FakeMessage(text="ایده")))

        idea = Idea.objects.get()
        assert f"/ideas/{idea.pk}" in recorder.sent[-1].text

    def test_a_photo_becomes_an_idea_with_an_image_attachment(
        self, recorder, linked_user: User
    ) -> None:
        handlers.handle_update(FakeUpdate(FakeMessage(photo=[FakePhotoSize()], caption="طرح جلد")))

        idea = Idea.objects.get()
        attachment = Attachment.objects.get()
        assert idea.title == "طرح جلد"
        assert attachment.kind == AttachmentKind.IMAGE
        assert attachment.thumbnail

    def test_a_photo_without_a_caption_still_gets_a_title(
        self, recorder, linked_user: User
    ) -> None:
        handlers.handle_update(FakeUpdate(FakeMessage(photo=[FakePhotoSize()])))

        assert Idea.objects.get().title == "عکس از تلگرام"

    def test_the_largest_size_of_a_photo_is_taken(self, recorder, linked_user: User) -> None:
        """Telegram sends several; the last is the biggest."""
        recorder.files["small"] = image_bytes(size=(90, 60))
        recorder.files["large"] = image_bytes(size=(900, 600))

        handlers.handle_update(
            FakeUpdate(
                FakeMessage(photo=[FakePhotoSize("small", "a"), FakePhotoSize("large", "b")])
            )
        )

        assert Attachment.objects.get().width == 900

    def test_a_file_that_is_not_really_an_image_is_rejected(
        self, recorder, linked_user: User
    ) -> None:
        """The bot is not a trusted source; the same inspectors run here."""
        recorder.files["photo-1"] = b"not an image at all"

        handlers.handle_update(FakeUpdate(FakeMessage(photo=[FakePhotoSize()])))

        assert Attachment.objects.count() == 0

    def test_an_empty_message_is_reported_as_unsupported(self, recorder, linked_user: User) -> None:
        handlers.handle_update(FakeUpdate(FakeMessage()))

        assert Idea.objects.count() == 0
        assert recorder.sent[-1].text == messages.UNSUPPORTED


class TestReminderButtons:
    @pytest.fixture
    def reminder(self, linked_user: User):
        idea = IdeaFactory(owner=linked_user, title="سری استوری")
        return reminder_services.set_reminder(
            idea=idea, recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )

    def test_done_finishes_the_idea_and_silences_the_reminder(self, recorder, reminder) -> None:
        handlers.handle_update(FakeUpdate(callback_query=FakeCallbackQuery(f"done:{reminder.pk}")))

        reminder.refresh_from_db()
        reminder.idea.refresh_from_db()
        assert reminder.idea.status == IdeaStatus.DONE
        assert reminder.is_active is False
        assert recorder.answered[-1] == messages.DONE_ACK

    def test_snooze_pushes_the_next_firing_an_hour_out(self, recorder, reminder) -> None:
        handlers.handle_update(
            FakeUpdate(callback_query=FakeCallbackQuery(f"snooze:{reminder.pk}"))
        )

        reminder.refresh_from_db()
        assert reminder.next_run_at > timezone.now() + timedelta(minutes=55)
        assert recorder.answered[-1] == messages.SNOOZED_ACK

    def test_mute_keeps_the_configuration(self, recorder, reminder) -> None:
        handlers.handle_update(FakeUpdate(callback_query=FakeCallbackQuery(f"mute:{reminder.pk}")))

        reminder.refresh_from_db()
        assert reminder.is_active is False
        assert reminder.hour == 9

    def test_the_buttons_are_retired_once_one_is_pressed(self, recorder, reminder) -> None:
        handlers.handle_update(FakeUpdate(callback_query=FakeCallbackQuery(f"mute:{reminder.pk}")))

        assert recorder.edited == [42]

    def test_another_user_s_reminder_cannot_be_touched(
        self, recorder, linked_user: User, other_user: User
    ) -> None:
        foreign = reminder_services.set_reminder(
            idea=IdeaFactory(owner=other_user),
            recurrence=ReminderRecurrence.DAILY,
            hour=9,
            minute=0,
        )

        handlers.handle_update(FakeUpdate(callback_query=FakeCallbackQuery(f"done:{foreign.pk}")))

        foreign.refresh_from_db()
        assert foreign.is_active is True
        assert recorder.answered[-1] == messages.STALE_ACK

    def test_a_deleted_reminder_answers_instead_of_crashing(
        self, recorder, linked_user: User
    ) -> None:
        handlers.handle_update(FakeUpdate(callback_query=FakeCallbackQuery("done:999999")))

        assert recorder.answered[-1] == messages.STALE_ACK

    def test_a_malformed_callback_is_survived(self, recorder, linked_user: User) -> None:
        handlers.handle_update(FakeUpdate(callback_query=FakeCallbackQuery("nonsense")))

        assert recorder.answered[-1] == messages.STALE_ACK


class TestReminderDelivery:
    def test_a_linked_user_is_reached_on_both_channels(self, recorder, linked_user: User) -> None:
        from apps.reminders.models import Reminder
        from apps.reminders.tasks import dispatch_due_reminders

        idea = IdeaFactory(owner=linked_user, title="سری استوری")
        reminder = reminder_services.set_reminder(
            idea=idea, recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )
        Reminder.objects.filter(pk=reminder.pk).update(
            next_run_at=timezone.now() - timedelta(seconds=30)
        )

        dispatch_due_reminders()

        assert Notification.objects.count() == 1
        assert recorder.sent[-1].chat_id == CHAT_ID
        assert "سری استوری" in recorder.sent[-1].text
        assert recorder.sent[-1].reply_markup is not None

    def test_an_unlinked_user_still_gets_the_in_app_notification(
        self, recorder, user: User
    ) -> None:
        """Telegram fails only its own delivery row."""
        from apps.reminders.models import Reminder, ReminderDelivery
        from apps.reminders.tasks import dispatch_due_reminders

        idea = IdeaFactory(owner=user)
        reminder = reminder_services.set_reminder(
            idea=idea, recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )
        Reminder.objects.filter(pk=reminder.pk).update(
            next_run_at=timezone.now() - timedelta(seconds=30)
        )

        dispatch_due_reminders()

        assert Notification.objects.count() == 1
        inapp = ReminderDelivery.objects.get(channel=DeliveryChannel.IN_APP)
        telegram = ReminderDelivery.objects.get(channel=DeliveryChannel.TELEGRAM)
        assert inapp.status == DeliveryStatus.SENT
        assert telegram.status == DeliveryStatus.FAILED

    def test_the_message_is_built_from_plain_text_not_the_document(
        self, recorder, linked_user: User
    ) -> None:
        from apps.ideas.services import create_idea

        idea = create_idea(
            owner=linked_user,
            title="عنوان",
            content={
                "type": "doc",
                "content": [
                    {
                        "type": "heading",
                        "attrs": {"level": 2},
                        "content": [{"type": "text", "text": "قاعده‌ها"}],
                    }
                ],
            },
        )
        reminder = reminder_services.set_reminder(
            idea=idea, recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )

        text = messages.reminder_text(reminder)

        assert "قاعده‌ها" in text
        assert "heading" not in text
        assert "<h2" not in text

    def test_user_text_is_escaped_before_it_meets_a_tag(self, recorder, linked_user: User) -> None:
        idea = IdeaFactory(owner=linked_user, title="<b>تقلبی</b> & دیگر")
        reminder = reminder_services.set_reminder(
            idea=idea, recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )

        text = messages.reminder_text(reminder)

        assert "&lt;b&gt;تقلبی&lt;/b&gt;" in text
        assert "&amp;" in text

    def test_the_keyboard_offers_the_four_designed_actions(
        self, recorder, linked_user: User
    ) -> None:
        idea = IdeaFactory(owner=linked_user)
        reminder = reminder_services.set_reminder(
            idea=idea, recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )

        labels = [
            button.text
            for row in messages.reminder_keyboard(reminder).inline_keyboard
            for button in row
        ]

        assert labels == [
            "انجام شد",
            "یادآوری یک ساعت بعد",
            "خاموش کردن یادآوری",
            "باز کردن در سایت",
        ]


class TestWebhookEndpoint:
    def test_a_request_without_the_secret_is_refused(self, api_client: APIClient, settings) -> None:
        settings.TELEGRAM_WEBHOOK_SECRET = "correct-secret"

        response = api_client.post(reverse("telegrambot:webhook"), {}, format="json")

        assert response.status_code == 403

    def test_a_wrong_secret_is_refused(self, api_client: APIClient, settings) -> None:
        response = api_client.post(
            reverse("telegrambot:webhook"),
            {},
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="wrong",
        )

        assert response.status_code == 403

    def test_an_unconfigured_secret_refuses_everything(
        self, api_client: APIClient, settings
    ) -> None:
        """The safe reading of "not configured" is to accept nothing."""
        settings.TELEGRAM_WEBHOOK_SECRET = ""

        response = api_client.post(
            reverse("telegrambot:webhook"),
            {},
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="",
        )

        assert response.status_code == 403

    def test_a_valid_secret_is_accepted_and_never_retried(
        self, api_client: APIClient, settings, monkeypatch
    ) -> None:
        """Anything but 200 makes Telegram redeliver the same update forever."""
        settings.TELEGRAM_WEBHOOK_SECRET = "correct-secret"
        monkeypatch.setattr("apps.telegrambot.views.bot.get_bot", lambda: None, raising=False)

        response = api_client.post(
            reverse("telegrambot:webhook"),
            {"update_id": 1},
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="correct-secret",
        )

        assert response.status_code == 200

    def test_a_broken_payload_still_answers_200(
        self, api_client: APIClient, settings, monkeypatch
    ) -> None:
        settings.TELEGRAM_WEBHOOK_SECRET = "correct-secret"
        monkeypatch.setattr("apps.telegrambot.views.bot.get_bot", lambda: None, raising=False)

        response = api_client.post(
            reverse("telegrambot:webhook"),
            {"nonsense": True},
            format="json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="correct-secret",
        )

        assert response.status_code == 200
