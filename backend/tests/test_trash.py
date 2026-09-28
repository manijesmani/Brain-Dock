"""The trash: deleting an idea moves it there, and only the trash deletes for good.

An idea in the trash is out of every listing, count, search and reminder,
comes back out exactly where it was, and is reachable by its own account
alone.
"""

from datetime import timedelta
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ideas.models import Attachment, AttachmentKind, Idea, IdeaStatus
from apps.ideas.services import create_attachment
from apps.notifications.models import Notification
from apps.notifications.tasks import send_stale_digests
from apps.reminders import services as reminder_services
from apps.reminders.models import Reminder, ReminderRecurrence
from apps.reminders.tasks import dispatch_due_reminders
from apps.users.models import User
from tests.factories import CategoryFactory, IdeaFactory, UserFactory
from tests.media_fixtures import image_upload

pytestmark = pytest.mark.django_db


def trash(client: APIClient, idea: Idea):
    return client.delete(reverse("ideas:idea-detail", args=[idea.pk]))


def listed_ids(client: APIClient, **params) -> list[int]:
    response = client.get(reverse("ideas:idea-list"), params)
    return [row["id"] for row in response.json()["results"]]


def trashed_ids(client: APIClient) -> list[int]:
    return [row["id"] for row in client.get(reverse("ideas:trash-list")).json()["results"]]


class TestMovingToTheTrash:
    def test_deleting_keeps_the_row_and_moves_it_to_the_trash(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)

        response = trash(auth_client, idea)

        assert response.status_code == 204
        idea.refresh_from_db()
        assert idea.deleted_at is not None
        assert trashed_ids(auth_client) == [idea.pk]

    def test_the_trash_lists_when_each_idea_was_deleted(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)
        trash(auth_client, idea)

        row = auth_client.get(reverse("ideas:trash-list")).json()["results"][0]

        assert row["title"] == idea.title
        assert row["deleted_at"] is not None

    def test_most_recently_deleted_comes_first(self, auth_client: APIClient, user: User) -> None:
        first, second = IdeaFactory(owner=user), IdeaFactory(owner=user)
        trash(auth_client, first)
        trash(auth_client, second)

        assert trashed_ids(auth_client) == [second.pk, first.pk]

    def test_deleting_is_not_an_edit(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        Idea.objects.filter(pk=idea.pk).update(updated_at=timezone.now() - timedelta(days=9))
        before = Idea.objects.get(pk=idea.pk).updated_at

        trash(auth_client, idea)

        assert Idea.objects.get(pk=idea.pk).updated_at == before


class TestLeftOutEverywhere:
    def test_not_listed_with_the_ideas_or_the_archive(
        self, auth_client: APIClient, user: User
    ) -> None:
        kept = IdeaFactory(owner=user)
        gone = IdeaFactory(owner=user)
        archived = IdeaFactory(owner=user, status=IdeaStatus.ARCHIVED)
        trash(auth_client, gone)
        trash(auth_client, archived)

        assert listed_ids(auth_client) == [kept.pk]
        assert listed_ids(auth_client, archived="true") == []

    def test_its_page_is_gone(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        trash(auth_client, idea)

        detail = reverse("ideas:idea-detail", args=[idea.pk])
        assert auth_client.get(detail).status_code == 404
        assert auth_client.patch(detail, {"title": "x"}, format="json").status_code == 404
        archive = reverse("ideas:idea-archive", args=[idea.pk])
        assert auth_client.post(archive).status_code == 404

    def test_not_found_by_search(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user, title="دفترچهٔ سفر به یزد")
        assert listed_ids(auth_client, search="یزد") == [idea.pk]

        trash(auth_client, idea)

        assert listed_ids(auth_client, search="یزد") == []

    def test_not_counted_in_categories_tags_or_the_account(
        self, auth_client: APIClient, user: User
    ) -> None:
        category = CategoryFactory(owner=user)
        idea = IdeaFactory(owner=user, category=category)
        IdeaFactory(owner=user, category=category)
        auth_client.patch(
            reverse("ideas:idea-detail", args=[idea.pk]), {"tags": ["سفر"]}, format="json"
        )

        trash(auth_client, idea)

        categories = auth_client.get(reverse("ideas:category-list")).json()["results"]
        tags = auth_client.get(reverse("ideas:tag-list")).json()["results"]
        me = auth_client.get(reverse("users:me")).json()
        assert categories[0]["idea_count"] == 1
        assert tags[0]["idea_count"] == 0
        assert me["idea_count"] == 1

    def test_not_among_the_stale_ideas(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        Idea.objects.filter(pk=idea.pk).update(updated_at=timezone.now() - timedelta(days=60))
        assert listed_ids(auth_client, stale="true") == [idea.pk]

        trash(auth_client, idea)

        assert listed_ids(auth_client, stale="true") == []
        send_stale_digests()
        assert not Notification.objects.filter(idea=idea).exists()

    def test_its_attachments_are_out_of_reach_until_it_comes_back(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)
        attachment = create_attachment(idea=idea, upload=image_upload(), kind=AttachmentKind.IMAGE)
        file_url = reverse("ideas:attachment-file", args=[attachment.pk])
        trash(auth_client, idea)

        assert auth_client.get(file_url).status_code == 404
        refused = auth_client.post(
            reverse("ideas:attachment-list"),
            {"idea": idea.pk, "kind": AttachmentKind.IMAGE, "file": image_upload()},
            format="multipart",
        )
        assert refused.status_code == 400

        auth_client.post(reverse("ideas:trash-restore", args=[idea.pk]))
        assert auth_client.get(file_url).status_code == 200


class TestReminders:
    def make_due(self, idea: Idea) -> Reminder:
        reminder = reminder_services.set_reminder(
            idea=idea, recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )
        Reminder.objects.filter(pk=reminder.pk).update(
            next_run_at=timezone.now() - timedelta(minutes=1)
        )
        return reminder

    def test_not_listed_while_the_idea_is_in_the_trash(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)
        self.make_due(idea)
        trash(auth_client, idea)

        listing = auth_client.get(reverse("reminders:reminder-list")).json()["results"]

        assert listing == []

    def test_not_sent_while_the_idea_is_in_the_trash(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)
        reminder = self.make_due(idea)
        trash(auth_client, idea)

        result = dispatch_due_reminders()

        assert result["fired"] == 0
        assert not Notification.objects.filter(owner=user).exists()
        # Kept as it was, to come back with the idea.
        reminder.refresh_from_db()
        assert reminder.is_active

    def test_sent_again_once_the_idea_is_back(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        self.make_due(idea)
        trash(auth_client, idea)
        auth_client.post(reverse("ideas:trash-restore", args=[idea.pk]))

        assert dispatch_due_reminders()["fired"] == 1

    def test_none_is_set_on_an_idea_in_the_trash(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        trash(auth_client, idea)

        response = auth_client.post(
            reverse("reminders:reminder-list"),
            {"idea": idea.pk, "recurrence": "daily", "hour": 9, "minute": 0},
            format="json",
        )

        assert response.status_code == 400


class TestRestoring:
    def test_comes_back_to_the_ideas(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user, status=IdeaStatus.PLANNED)
        trash(auth_client, idea)

        response = auth_client.post(reverse("ideas:trash-restore", args=[idea.pk]))

        assert response.status_code == 200
        assert response.json()["status"] == IdeaStatus.PLANNED
        assert listed_ids(auth_client) == [idea.pk]
        assert trashed_ids(auth_client) == []

    def test_an_archived_idea_comes_back_to_the_archive(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user, status=IdeaStatus.ARCHIVED)
        trash(auth_client, idea)

        auth_client.post(reverse("ideas:trash-restore", args=[idea.pk]))

        assert listed_ids(auth_client, archived="true") == [idea.pk]
        assert listed_ids(auth_client) == []

    def test_restoring_asks_for_a_place_within_the_limit(self) -> None:
        free = UserFactory(is_premium=False)
        client = APIClient()
        client.force_authenticate(user=free)
        gone = IdeaFactory(owner=free)
        trash(client, gone)
        IdeaFactory(owner=free)
        IdeaFactory(owner=free)

        refused = client.post(reverse("ideas:trash-restore", args=[gone.pk]))

        assert refused.status_code == 403
        assert refused.json()["code"] == "idea_limit_reached"
        assert trashed_ids(client) == [gone.pk]


class TestDeletingForGood:
    def test_removes_the_row(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        trash(auth_client, idea)

        response = auth_client.delete(reverse("ideas:trash-detail", args=[idea.pk]))

        assert response.status_code == 204
        assert not Idea.objects.filter(pk=idea.pk).exists()

    def test_removes_its_files_too(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        attachment = create_attachment(idea=idea, upload=image_upload(), kind=AttachmentKind.IMAGE)
        path = Path(attachment.file.path)
        trash(auth_client, idea)
        assert path.exists()

        auth_client.delete(reverse("ideas:trash-detail", args=[idea.pk]))

        assert not Attachment.objects.exists()
        assert not path.exists()

    def test_only_from_the_trash(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)

        response = auth_client.delete(reverse("ideas:trash-detail", args=[idea.pk]))

        assert response.status_code == 404
        assert Idea.objects.filter(pk=idea.pk).exists()

    def test_nothing_empties_the_trash_on_its_own(self, settings) -> None:
        tasks = [entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()]

        assert not any("trash" in task or "purge" in task for task in tasks)


class TestOwnership:
    """Every action on the trash reaches the requesting account's own ideas only."""

    def test_another_accounts_idea_cannot_be_moved_to_the_trash(
        self, auth_client: APIClient, other_user: User
    ) -> None:
        foreign = IdeaFactory(owner=other_user)

        assert trash(auth_client, foreign).status_code == 404
        foreign.refresh_from_db()
        assert foreign.deleted_at is None

    def test_another_accounts_trash_is_not_listed(
        self, auth_client: APIClient, other_user: User
    ) -> None:
        IdeaFactory(owner=other_user, deleted_at=timezone.now())

        assert trashed_ids(auth_client) == []

    def test_another_accounts_idea_cannot_be_restored(
        self, auth_client: APIClient, other_user: User
    ) -> None:
        foreign = IdeaFactory(owner=other_user, deleted_at=timezone.now())

        response = auth_client.post(reverse("ideas:trash-restore", args=[foreign.pk]))

        assert response.status_code == 404
        foreign.refresh_from_db()
        assert foreign.deleted_at is not None

    def test_another_accounts_idea_cannot_be_deleted_for_good(
        self, auth_client: APIClient, other_user: User
    ) -> None:
        foreign = IdeaFactory(owner=other_user, deleted_at=timezone.now())

        response = auth_client.delete(reverse("ideas:trash-detail", args=[foreign.pk]))

        assert response.status_code == 404
        assert Idea.objects.filter(pk=foreign.pk).exists()

    def test_the_trash_needs_a_session(self, api_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user, deleted_at=timezone.now())

        assert api_client.get(reverse("ideas:trash-list")).status_code == 403
        assert api_client.post(reverse("ideas:trash-restore", args=[idea.pk])).status_code == 403
        assert api_client.delete(reverse("ideas:trash-detail", args=[idea.pk])).status_code == 403
