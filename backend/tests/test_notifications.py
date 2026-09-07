import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.notifications.models import Notification, NotificationKind
from apps.users.models import User
from tests.factories import IdeaFactory

pytestmark = pytest.mark.django_db


def make_notification(user: User, **overrides) -> Notification:
    return Notification.objects.create(
        owner=user,
        kind=overrides.pop("kind", NotificationKind.REMINDER),
        text=overrides.pop("text", "یادآوری: عنوان، هر روز ساعت ۹:۰۰"),
        **overrides,
    )


class TestListing:
    def test_newest_first(self, auth_client: APIClient, user: User) -> None:
        make_notification(user, text="اولی")
        make_notification(user, text="دومی")

        texts = [
            row["text"]
            for row in auth_client.get(reverse("notifications:notification-list")).json()["results"]
        ]

        assert texts == ["دومی", "اولی"]

    def test_only_the_owner_sees_them(
        self, auth_client: APIClient, user: User, other_user: User
    ) -> None:
        make_notification(user, text="مال من")
        make_notification(other_user, text="مال دیگری")

        response = auth_client.get(reverse("notifications:notification-list"))

        assert [row["text"] for row in response.json()["results"]] == ["مال من"]

    def test_unread_only(self, auth_client: APIClient, user: User) -> None:
        make_notification(user, text="نخوانده")
        make_notification(user, text="خوانده", is_read=True)

        response = auth_client.get(reverse("notifications:notification-list"), {"unread": "true"})

        assert [row["text"] for row in response.json()["results"]] == ["نخوانده"]

    def test_anonymous_access_is_refused(self, api_client: APIClient) -> None:
        assert api_client.get(reverse("notifications:notification-list")).status_code == 403


class TestUnreadCount:
    def test_it_counts_only_unread_ones_of_this_owner(
        self, auth_client: APIClient, user: User, other_user: User
    ) -> None:
        make_notification(user)
        make_notification(user)
        make_notification(user, is_read=True)
        make_notification(other_user)

        response = auth_client.get(reverse("notifications:notification-unread-count"))

        assert response.json() == {"count": 2}


class TestMarkingRead:
    def test_marking_one(self, auth_client: APIClient, user: User) -> None:
        notification = make_notification(user)

        response = auth_client.post(
            reverse("notifications:notification-read", args=[notification.pk])
        )

        assert response.status_code == 200
        notification.refresh_from_db()
        assert notification.is_read is True
        assert notification.read_at is not None

    def test_marking_an_already_read_one_keeps_the_original_timestamp(
        self, auth_client: APIClient, user: User
    ) -> None:
        notification = make_notification(user)
        auth_client.post(reverse("notifications:notification-read", args=[notification.pk]))
        notification.refresh_from_db()
        first_read_at = notification.read_at

        auth_client.post(reverse("notifications:notification-read", args=[notification.pk]))
        notification.refresh_from_db()

        assert notification.read_at == first_read_at

    def test_marking_all(self, auth_client: APIClient, user: User) -> None:
        make_notification(user)
        make_notification(user)
        make_notification(user, is_read=True)

        response = auth_client.post(reverse("notifications:notification-read-all"))

        assert response.json() == {"updated": 2}
        assert Notification.objects.filter(owner=user, is_read=False).count() == 0

    def test_marking_all_leaves_other_owners_alone(
        self, auth_client: APIClient, user: User, other_user: User
    ) -> None:
        make_notification(user)
        make_notification(other_user)

        auth_client.post(reverse("notifications:notification-read-all"))

        assert Notification.objects.filter(owner=other_user, is_read=False).count() == 1

    def test_another_users_notification_is_not_found(
        self, auth_client: APIClient, other_user: User
    ) -> None:
        foreign = make_notification(other_user)

        response = auth_client.post(reverse("notifications:notification-read", args=[foreign.pk]))

        assert response.status_code == 404


class TestIdeaLink:
    def test_a_notification_points_at_its_idea(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        make_notification(user, idea=idea)

        row = auth_client.get(reverse("notifications:notification-list")).json()["results"][0]

        assert row["idea"] == idea.pk

    def test_deleting_the_idea_keeps_the_notification(self, user: User) -> None:
        """The history stays intact; the row simply stops being a link."""
        idea = IdeaFactory(owner=user)
        notification = make_notification(user, idea=idea)

        idea.delete()
        notification.refresh_from_db()

        assert notification.idea is None
        assert Notification.objects.count() == 1
