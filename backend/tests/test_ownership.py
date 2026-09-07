"""Cross-tenant isolation.

The data model is multi-user from day one, so every collection has to prove
that one account can neither read nor reach another account's records. A
foreign record is expected to answer 404 rather than 403: the queryset is
narrowed before the object is looked up, so its existence is never disclosed.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.ideas.models import Idea, IdeaStatus
from apps.users.models import User
from tests.factories import CategoryFactory, IdeaFactory, TagFactory

pytestmark = pytest.mark.django_db


class TestIdeaIsolation:
    def test_listing_excludes_other_users_ideas(
        self, auth_client: APIClient, user: User, other_user: User
    ) -> None:
        IdeaFactory(owner=user, title="مال من")
        IdeaFactory(owner=other_user, title="مال دیگری")

        titles = [
            row["title"] for row in auth_client.get(reverse("ideas:idea-list")).json()["results"]
        ]

        assert titles == ["مال من"]

    def test_reading_another_users_idea_is_not_found(
        self, auth_client: APIClient, other_user: User
    ) -> None:
        foreign = IdeaFactory(owner=other_user)

        response = auth_client.get(reverse("ideas:idea-detail", args=[foreign.pk]))

        assert response.status_code == 404

    def test_updating_another_users_idea_is_not_found(
        self, auth_client: APIClient, other_user: User
    ) -> None:
        foreign = IdeaFactory(owner=other_user, title="دست‌نخورده")

        response = auth_client.patch(
            reverse("ideas:idea-detail", args=[foreign.pk]),
            {"title": "دستکاری شد"},
            format="json",
        )

        assert response.status_code == 404
        foreign.refresh_from_db()
        assert foreign.title == "دست‌نخورده"

    def test_deleting_another_users_idea_is_not_found(
        self, auth_client: APIClient, other_user: User
    ) -> None:
        foreign = IdeaFactory(owner=other_user)

        response = auth_client.delete(reverse("ideas:idea-detail", args=[foreign.pk]))

        assert response.status_code == 404
        assert Idea.objects.filter(pk=foreign.pk).exists()

    def test_archiving_another_users_idea_is_not_found(
        self, auth_client: APIClient, other_user: User
    ) -> None:
        foreign = IdeaFactory(owner=other_user, status=IdeaStatus.IDEA)

        response = auth_client.post(reverse("ideas:idea-archive", args=[foreign.pk]))

        assert response.status_code == 404
        foreign.refresh_from_db()
        assert foreign.status == IdeaStatus.IDEA


class TestCategoryIsolation:
    def test_listing_excludes_other_users_categories(
        self, auth_client: APIClient, user: User, other_user: User
    ) -> None:
        CategoryFactory(owner=user, name="مال من")
        CategoryFactory(owner=other_user, name="مال دیگری")

        names = [
            row["name"] for row in auth_client.get(reverse("ideas:category-list")).json()["results"]
        ]

        assert names == ["مال من"]

    def test_an_idea_cannot_be_filed_under_a_foreign_category(
        self, auth_client: APIClient, other_user: User
    ) -> None:
        foreign = CategoryFactory(owner=other_user)

        response = auth_client.post(
            reverse("ideas:idea-list"),
            {"title": "عنوان", "category": foreign.pk},
            format="json",
        )

        assert response.status_code == 400
        assert "category" in response.json()["errors"]


class TestTagIsolation:
    def test_listing_excludes_other_users_tags(
        self, auth_client: APIClient, user: User, other_user: User
    ) -> None:
        TagFactory(owner=user, name="مال‌من")
        TagFactory(owner=other_user, name="مال‌دیگری")

        names = [
            row["name"] for row in auth_client.get(reverse("ideas:tag-list")).json()["results"]
        ]

        assert names == ["مال‌من"]

    def test_an_identical_tag_name_creates_a_separate_record_per_owner(
        self, auth_client: APIClient, user: User, other_user: User
    ) -> None:
        TagFactory(owner=other_user, name="مشترک")

        auth_client.post(
            reverse("ideas:idea-list"),
            {"title": "عنوان", "tags": ["مشترک"]},
            format="json",
        )

        idea = Idea.objects.get(owner=user)
        assert idea.tags.get().owner == user


class TestAuthenticationRequired:
    @pytest.mark.parametrize(
        "route",
        ["ideas:idea-list", "ideas:category-list", "ideas:tag-list"],
    )
    def test_anonymous_access_is_refused(self, api_client: APIClient, route: str) -> None:
        assert api_client.get(reverse(route)).status_code == 403
