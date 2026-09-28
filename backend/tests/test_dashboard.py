"""The queries the dashboard and the settings page depend on.

Phase 5 added three read paths that no earlier phase covered: the stale
filter, the two reminder windows, and Telegram account linking.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ideas.models import Idea, IdeaStatus
from apps.reminders import services as reminder_services
from apps.reminders.models import ReminderRecurrence
from apps.telegrambot.models import TelegramLinkToken
from apps.users.models import User
from core.formatting import user_timezone
from tests.factories import IdeaFactory

pytestmark = pytest.mark.django_db


def age(idea: Idea, days: int) -> Idea:
    """Backdates an idea past the owner's staleness threshold."""
    moment = timezone.now() - timedelta(days=days)
    Idea.objects.filter(pk=idea.pk).update(updated_at=moment, created_at=moment)
    idea.refresh_from_db()
    return idea


class TestStaleFilter:
    def test_it_finds_ideas_untouched_for_longer_than_the_threshold(
        self, auth_client: APIClient, user: User
    ) -> None:
        age(IdeaFactory(owner=user, title="فراموش‌شده", status=IdeaStatus.IDEA), 30)
        IdeaFactory(owner=user, title="تازه", status=IdeaStatus.IDEA)

        response = auth_client.get(reverse("ideas:idea-list"), {"stale": "true"})

        assert [row["title"] for row in response.json()["results"]] == ["فراموش‌شده"]

    def test_finished_and_in_progress_ideas_are_never_stale(
        self, auth_client: APIClient, user: User
    ) -> None:
        """Something being worked on or already done is not being neglected."""
        age(IdeaFactory(owner=user, status=IdeaStatus.DONE), 60)
        age(IdeaFactory(owner=user, status=IdeaStatus.DOING), 60)

        response = auth_client.get(reverse("ideas:idea-list"), {"stale": "true"})

        assert response.json()["pagination"]["count"] == 0

    def test_the_threshold_is_the_owner_s_own(self, auth_client: APIClient, user: User) -> None:
        age(IdeaFactory(owner=user, title="بیست روزه", status=IdeaStatus.IDEA), 20)

        assert (
            auth_client.get(reverse("ideas:idea-list"), {"stale": "true"}).json()["pagination"][
                "count"
            ]
            == 1
        )

        user.stale_after_days = 30
        user.save(update_fields=["stale_after_days"])

        assert (
            auth_client.get(reverse("ideas:idea-list"), {"stale": "true"}).json()["pagination"][
                "count"
            ]
            == 0
        )

    def test_stale_false_returns_the_complement(self, auth_client: APIClient, user: User) -> None:
        age(IdeaFactory(owner=user, title="کهنه", status=IdeaStatus.IDEA), 30)
        IdeaFactory(owner=user, title="تازه", status=IdeaStatus.IDEA)

        response = auth_client.get(reverse("ideas:idea-list"), {"stale": "false"})

        assert [row["title"] for row in response.json()["results"]] == ["تازه"]


class TestReminderWindows:
    def test_today_includes_a_daily_reminder_whose_time_has_passed(
        self, auth_client: APIClient, user: User
    ) -> None:
        """The section is the day's agenda, not what is left of it, so a
        reminder already delivered this morning still belongs there."""
        idea = IdeaFactory(owner=user, title="روزانه")
        reminder_services.set_reminder(
            idea=idea, recurrence=ReminderRecurrence.DAILY, hour=0, minute=0
        )

        response = auth_client.get(reverse("reminders:reminder-list"), {"window": "today"})

        assert [row["idea_title"] for row in response.json()["results"]] == ["روزانه"]

    def test_today_excludes_a_reminder_that_does_not_fire_today(
        self, auth_client: APIClient, user: User
    ) -> None:
        today = timezone.now().astimezone(user_timezone())
        # A weekly rule set to the day after tomorrow cannot land today.
        weekday = (((today.weekday() + 1) % 7) + 2) % 7

        idea = IdeaFactory(owner=user)
        reminder_services.set_reminder(
            idea=idea,
            recurrence=ReminderRecurrence.WEEKLY,
            hour=9,
            minute=0,
            weekdays=[weekday],
        )

        response = auth_client.get(reverse("reminders:reminder-list"), {"window": "today"})

        assert response.json()["pagination"]["count"] == 0

    def test_the_week_window_excludes_what_today_already_shows(
        self, auth_client: APIClient, user: User
    ) -> None:
        """A daily reminder would otherwise appear in both sections."""
        idea = IdeaFactory(owner=user)
        reminder_services.set_reminder(
            idea=idea, recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )

        week = auth_client.get(reverse("reminders:reminder-list"), {"window": "week"})

        assert week.json()["pagination"]["count"] == 0

    def test_a_paused_reminder_appears_in_neither_window(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)
        reminder = reminder_services.set_reminder(
            idea=idea, recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )
        reminder_services.set_active(reminder=reminder, is_active=False)

        for window in ("today", "week"):
            response = auth_client.get(reverse("reminders:reminder-list"), {"window": window})
            assert response.json()["pagination"]["count"] == 0

    def test_a_window_never_crosses_owners(
        self, auth_client: APIClient, user: User, other_user: User
    ) -> None:
        reminder_services.set_reminder(
            idea=IdeaFactory(owner=other_user),
            recurrence=ReminderRecurrence.DAILY,
            hour=9,
            minute=0,
        )

        response = auth_client.get(reverse("reminders:reminder-list"), {"window": "today"})

        assert response.json()["pagination"]["count"] == 0

    def test_the_row_carries_its_idea_so_the_dashboard_needs_one_request(
        self, auth_client: APIClient, user: User
    ) -> None:
        from tests.factories import CategoryFactory

        category = CategoryFactory(owner=user, name="وب‌سایت")
        idea = IdeaFactory(owner=user, title="بازطراحی", category=category)
        reminder_services.set_reminder(
            idea=idea, recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )

        row = auth_client.get(reverse("reminders:reminder-list")).json()["results"][0]

        assert row["idea_title"] == "بازطراحی"
        assert row["idea_category_name"] == "وب‌سایت"
        assert row["idea_category_color"] == category.color


class TestTelegramLinking:
    @pytest.fixture(autouse=True)
    def site_owner(self, user: User) -> None:
        """The Telegram section is the owner's alone; see tests/test_plans.py."""
        user.is_superuser = True
        user.save(update_fields=["is_superuser"])

    def test_it_reports_an_unlinked_account(self, auth_client: APIClient) -> None:
        response = auth_client.get(reverse("telegrambot:link"))

        assert response.json()["is_linked"] is False
        assert response.json()["link"] is None

    def test_creating_a_link_returns_a_one_time_deep_link(
        self, auth_client: APIClient, user: User
    ) -> None:
        response = auth_client.post(reverse("telegrambot:link"))

        assert response.status_code == 201
        link = response.json()["link"]
        assert link.startswith("t.me/")
        assert "?start=" in link
        assert TelegramLinkToken.objects.filter(user=user).count() == 1

    def test_a_new_link_invalidates_the_previous_one(
        self, auth_client: APIClient, user: User
    ) -> None:
        """An old link left working would be a second key to the same door."""
        auth_client.post(reverse("telegrambot:link"))
        first = TelegramLinkToken.objects.get()

        auth_client.post(reverse("telegrambot:link"))
        first.refresh_from_db()

        assert first.is_usable is False
        assert TelegramLinkToken.objects.filter(user=user).count() == 2

    def test_an_expired_token_is_not_offered(self, auth_client: APIClient, user: User) -> None:
        auth_client.post(reverse("telegrambot:link"))
        TelegramLinkToken.objects.update(expires_at=timezone.now() - timedelta(minutes=1))

        assert auth_client.get(reverse("telegrambot:link")).json()["link"] is None

    def test_disconnecting_clears_the_chat_and_revokes_the_link(
        self, auth_client: APIClient, user: User
    ) -> None:
        user.telegram_chat_id = 123456789
        user.telegram_linked_at = timezone.now()
        user.save(update_fields=["telegram_chat_id", "telegram_linked_at"])
        auth_client.post(reverse("telegrambot:link"))

        response = auth_client.delete(reverse("telegrambot:link"))

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.telegram_chat_id is None
        assert user.telegram_linked_at is None
        assert (
            TelegramLinkToken.objects.filter(user=user, used_at__isnull=True).first().is_usable
            is False
        )

    def test_anonymous_access_is_refused(self, api_client: APIClient) -> None:
        assert api_client.get(reverse("telegrambot:link")).status_code == 403

    def test_a_token_belongs_to_exactly_one_account(
        self, auth_client: APIClient, user: User, other_user: User
    ) -> None:
        auth_client.post(reverse("telegrambot:link"))

        assert TelegramLinkToken.objects.filter(user=other_user).count() == 0
