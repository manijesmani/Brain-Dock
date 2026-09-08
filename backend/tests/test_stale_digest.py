"""The stale-idea alert.

Deliberately not a reminder: nobody asked for this on any particular idea.
It is the product noticing on its own that ideas have gone quiet, so the
things worth proving are that it notices the right ones, that it says so once
rather than every day, and that editing an idea makes it eligible again.
"""

from dataclasses import dataclass, field
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.ideas.models import Idea, IdeaStatus
from apps.ideas.services import update_idea
from apps.notifications.models import Notification, NotificationKind, StaleAlert
from apps.notifications.tasks import send_stale_digests
from apps.users.models import User
from tests.factories import IdeaFactory

pytestmark = pytest.mark.django_db

CHAT_ID = 4242424


def age(idea: Idea, days: int) -> Idea:
    """Backdates an idea so it counts as neglected."""
    moment = timezone.now() - timedelta(days=days)
    Idea.objects.filter(pk=idea.pk).update(updated_at=moment, created_at=moment)
    idea.refresh_from_db()
    return idea


@dataclass
class BotRecorder:
    sent: list = field(default_factory=list)

    def send_message(self, *, chat_id, text, reply_markup=None):
        self.sent.append(text)


@pytest.fixture
def recorder(monkeypatch) -> BotRecorder:
    recording = BotRecorder()
    monkeypatch.setattr("apps.notifications.channels.telegram.bot", recording, raising=False)
    return recording


@pytest.fixture
def linked_user(user: User) -> User:
    user.telegram_chat_id = CHAT_ID
    user.telegram_linked_at = timezone.now()
    user.save(update_fields=["telegram_chat_id", "telegram_linked_at"])
    return user


class TestWhatCounts:
    def test_a_neglected_idea_is_reported(self, recorder, user: User) -> None:
        age(IdeaFactory(owner=user, title="فراموش‌شده", status=IdeaStatus.IDEA), 30)

        result = send_stale_digests()

        assert result["ideas"] == 1
        notification = Notification.objects.get()
        assert notification.kind == NotificationKind.STALE
        assert "«فراموش‌شده»" in notification.text
        assert "روز بدون تغییر مانده" in notification.text

    def test_a_recently_touched_idea_is_not(self, recorder, user: User) -> None:
        IdeaFactory(owner=user, status=IdeaStatus.IDEA)

        assert send_stale_digests()["ideas"] == 0
        assert Notification.objects.count() == 0

    @pytest.mark.parametrize("status", [IdeaStatus.DOING, IdeaStatus.DONE])
    def test_work_in_progress_and_finished_ideas_are_never_stale(
        self, recorder, user: User, status: str
    ) -> None:
        """Something being worked on or already done is not being neglected."""
        age(IdeaFactory(owner=user, status=status), 60)

        assert send_stale_digests()["ideas"] == 0

    def test_an_archived_idea_is_not_reported(self, recorder, user: User) -> None:
        age(IdeaFactory(owner=user, status=IdeaStatus.ARCHIVED), 60)

        assert send_stale_digests()["ideas"] == 0

    def test_the_threshold_is_the_owner_s_own(self, recorder, user: User) -> None:
        age(IdeaFactory(owner=user, status=IdeaStatus.IDEA), 20)

        user.stale_after_days = 30
        user.save(update_fields=["stale_after_days"])
        assert send_stale_digests()["ideas"] == 0

        user.stale_after_days = 14
        user.save(update_fields=["stale_after_days"])
        assert send_stale_digests()["ideas"] == 1

    def test_the_notification_names_the_number_of_days(self, recorder, user: User) -> None:
        age(IdeaFactory(owner=user, title="ایده", status=IdeaStatus.IDEA), 23)

        send_stale_digests()

        # Persian digits, as everywhere else the user reads a number.
        assert "۲۳ روز" in Notification.objects.get().text

    def test_each_owner_hears_only_about_their_own(
        self, recorder, user: User, other_user: User
    ) -> None:
        age(IdeaFactory(owner=user, title="مال من", status=IdeaStatus.IDEA), 30)
        age(IdeaFactory(owner=other_user, title="مال دیگری", status=IdeaStatus.IDEA), 30)

        send_stale_digests()

        assert Notification.objects.get(owner=user).text.startswith("«مال من»")
        assert Notification.objects.get(owner=other_user).text.startswith("«مال دیگری»")


class TestSayingItOnce:
    """The job runs every day; the same list must not arrive every day."""

    def test_a_second_run_reports_nothing_new(self, recorder, user: User) -> None:
        age(IdeaFactory(owner=user, status=IdeaStatus.IDEA), 30)

        send_stale_digests()
        second = send_stale_digests()

        assert second["ideas"] == 0
        assert Notification.objects.count() == 1

    def test_a_run_records_that_it_reported(self, recorder, user: User) -> None:
        idea = age(IdeaFactory(owner=user, status=IdeaStatus.IDEA), 30)

        send_stale_digests()

        alert = StaleAlert.objects.get()
        assert alert.idea == idea
        assert alert.notified_at >= idea.updated_at

    def test_editing_an_idea_makes_it_eligible_again(self, recorder, user: User) -> None:
        """A fresh period of neglect is worth mentioning afresh.

        Time is simulated by moving both records back together, keeping their
        real order: the alert was written first, the edit came after it, and
        the idea has been quiet ever since.
        """
        idea = age(IdeaFactory(owner=user, status=IdeaStatus.IDEA), 60)
        send_stale_digests()

        # Reported forty-five days ago...
        StaleAlert.objects.update(notified_at=timezone.now() - timedelta(days=45))
        # ...the user opened it thirty days ago, and then abandoned it again.
        update_idea(idea=idea, title="عنوان تازه")
        age(idea, 30)

        assert send_stale_digests()["ideas"] == 1
        assert Notification.objects.count() == 2

    def test_an_idea_edited_but_not_yet_stale_again_is_silent(self, recorder, user: User) -> None:
        idea = age(IdeaFactory(owner=user, status=IdeaStatus.IDEA), 30)
        send_stale_digests()

        update_idea(idea=idea, title="عنوان تازه")

        assert send_stale_digests()["ideas"] == 0

    def test_deleting_an_idea_takes_its_alert_with_it(self, recorder, user: User) -> None:
        idea = age(IdeaFactory(owner=user, status=IdeaStatus.IDEA), 30)
        send_stale_digests()

        idea.delete()

        assert StaleAlert.objects.count() == 0


class TestTelegramDigest:
    def test_a_linked_user_gets_one_summary_not_one_message_each(
        self, recorder, linked_user: User
    ) -> None:
        """A chat wants a list, not ten separate pings."""
        for index in range(3):
            age(IdeaFactory(owner=linked_user, title=f"ایده {index}", status=IdeaStatus.IDEA), 30)

        result = send_stale_digests()

        assert result["telegram_deliveries"] == 1
        assert len(recorder.sent) == 1
        for index in range(3):
            assert f"ایده {index}" in recorder.sent[0]

    def test_the_in_app_side_stays_one_row_per_idea(self, recorder, linked_user: User) -> None:
        """Each row links to its own idea, which is how the design draws it."""
        for _ in range(3):
            age(IdeaFactory(owner=linked_user, status=IdeaStatus.IDEA), 30)

        send_stale_digests()

        assert Notification.objects.count() == 3
        assert all(n.idea is not None for n in Notification.objects.all())

    def test_an_unlinked_user_still_gets_the_in_app_notifications(
        self, recorder, user: User
    ) -> None:
        age(IdeaFactory(owner=user, status=IdeaStatus.IDEA), 30)

        result = send_stale_digests()

        assert result["ideas"] == 1
        assert result["telegram_deliveries"] == 0
        assert Notification.objects.count() == 1
        assert recorder.sent == []

    def test_a_telegram_failure_does_not_lose_the_in_app_notification(
        self, monkeypatch, linked_user: User
    ) -> None:
        class Broken:
            def send_message(self, **kwargs):
                raise RuntimeError("Telegram is down")

        monkeypatch.setattr("apps.notifications.channels.telegram.bot", Broken(), raising=False)
        age(IdeaFactory(owner=linked_user, status=IdeaStatus.IDEA), 30)

        result = send_stale_digests()

        assert result["telegram_deliveries"] == 0
        assert Notification.objects.count() == 1

    def test_the_digest_escapes_user_text(self, recorder, linked_user: User) -> None:
        age(IdeaFactory(owner=linked_user, title="<b>تقلبی</b>", status=IdeaStatus.IDEA), 30)

        send_stale_digests()

        assert "&lt;b&gt;" in recorder.sent[0]
        assert "<b>تقلبی</b>" not in recorder.sent[0]

    def test_a_long_list_is_capped(self, recorder, linked_user: User) -> None:
        """A summary that runs to fifty lines is not a summary."""
        from apps.notifications.tasks import DIGEST_LIMIT

        for _ in range(DIGEST_LIMIT + 5):
            age(IdeaFactory(owner=linked_user, status=IdeaStatus.IDEA), 30)

        send_stale_digests()

        assert recorder.sent[0].count("•") == DIGEST_LIMIT


class TestScheduling:
    def test_the_job_is_registered_once_a_day(self, settings) -> None:
        entry = settings.CELERY_BEAT_SCHEDULE["send-stale-digests"]

        assert entry["task"] == "notifications.send_stale_digests"
        # 05:30 UTC is 09:00 in Tehran.
        assert entry["schedule"].hour == {5}
        assert entry["schedule"].minute == {30}

    def test_it_is_separate_from_the_reminder_tick(self, settings) -> None:
        """A stale alert is not a reminder, and does not share its schedule."""
        assert "dispatch-due-reminders" in settings.CELERY_BEAT_SCHEDULE
        assert "send-stale-digests" in settings.CELERY_BEAT_SCHEDULE
