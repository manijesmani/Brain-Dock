import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.ideas.models import Category, Idea, IdeaStatus, Tag
from apps.users.models import User
from tests.factories import CategoryFactory, IdeaFactory

pytestmark = pytest.mark.django_db


def doc(*paragraphs: str) -> dict:
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": line}]}
            for line in paragraphs
        ],
    }


class TestCreateIdea:
    def test_minimal_payload_creates_an_idea(self, auth_client: APIClient, user: User) -> None:
        response = auth_client.post(
            reverse("ideas:idea-list"), {"title": "  ایدهٔ تازه  "}, format="json"
        )

        assert response.status_code == 201
        idea = Idea.objects.get(pk=response.json()["id"])
        assert idea.owner == user
        assert idea.title == "ایدهٔ تازه"
        assert idea.status == IdeaStatus.IDEA

    def test_plain_text_is_derived_from_the_document(self, auth_client: APIClient) -> None:
        response = auth_client.post(
            reverse("ideas:idea-list"),
            {"title": "عنوان", "content": doc("خط اول", "خط دوم")},
            format="json",
        )

        assert response.status_code == 201
        assert Idea.objects.get(pk=response.json()["id"]).plain_text == "خط اول\nخط دوم"

    def test_client_supplied_plain_text_is_ignored(self, auth_client: APIClient) -> None:
        response = auth_client.post(
            reverse("ideas:idea-list"),
            {"title": "عنوان", "content": doc("واقعی"), "plain_text": "جعلی"},
            format="json",
        )

        assert Idea.objects.get(pk=response.json()["id"]).plain_text == "واقعی"

    def test_disallowed_content_is_stripped_before_storage(self, auth_client: APIClient) -> None:
        payload = {
            "type": "doc",
            "content": [
                {
                    "type": "script",
                    "content": [{"type": "text", "text": "alert(1)"}],
                }
            ],
        }

        response = auth_client.post(
            reverse("ideas:idea-list"),
            {"title": "عنوان", "content": payload},
            format="json",
        )

        # The script wrapper is gone and its text is re-wrapped in a
        # paragraph, so the stored document stays structurally valid.
        stored = Idea.objects.get(pk=response.json()["id"]).content
        assert stored == {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "alert(1)"}],
                }
            ],
        }

    def test_empty_title_is_rejected(self, auth_client: APIClient) -> None:
        response = auth_client.post(reverse("ideas:idea-list"), {"title": "   "}, format="json")

        assert response.status_code == 400

    def test_tags_are_created_on_demand(self, auth_client: APIClient, user: User) -> None:
        response = auth_client.post(
            reverse("ideas:idea-list"),
            {"title": "عنوان", "tags": ["ریلز", "آموزشی"]},
            format="json",
        )

        assert response.status_code == 201
        assert sorted(response.json()["tags"]) == sorted(["ریلز", "آموزشی"])
        assert Tag.objects.filter(owner=user).count() == 2

    def test_repeating_a_tag_reuses_the_existing_record(
        self, auth_client: APIClient, user: User
    ) -> None:
        url = reverse("ideas:idea-list")
        auth_client.post(url, {"title": "اول", "tags": ["React"]}, format="json")
        auth_client.post(url, {"title": "دوم", "tags": ["react"]}, format="json")

        assert Tag.objects.filter(owner=user).count() == 1

    def test_archived_status_cannot_be_set_directly(self, auth_client: APIClient) -> None:
        response = auth_client.post(
            reverse("ideas:idea-list"),
            {"title": "عنوان", "status": IdeaStatus.ARCHIVED},
            format="json",
        )

        assert response.status_code == 400


class TestListIdeas:
    def test_archived_ideas_are_hidden_by_default(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user, title="فعال")
        IdeaFactory(owner=user, title="بایگانی", status=IdeaStatus.ARCHIVED)

        titles = [
            row["title"] for row in auth_client.get(reverse("ideas:idea-list")).json()["results"]
        ]

        assert titles == ["فعال"]

    def test_archive_listing_shows_only_archived_ideas(
        self, auth_client: APIClient, user: User
    ) -> None:
        IdeaFactory(owner=user, title="فعال")
        IdeaFactory(owner=user, title="بایگانی", status=IdeaStatus.ARCHIVED)

        response = auth_client.get(reverse("ideas:idea-list"), {"archived": "true"})

        assert [row["title"] for row in response.json()["results"]] == ["بایگانی"]

    def test_list_payload_omits_the_full_document(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user)

        row = auth_client.get(reverse("ideas:idea-list")).json()["results"][0]

        assert "content" not in row
        assert "plain_text" in row

    def test_response_is_paginated(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory.create_batch(3, owner=user)

        body = auth_client.get(reverse("ideas:idea-list")).json()

        assert body["pagination"]["count"] == 3
        assert body["pagination"]["page"] == 1


class TestUpdateIdea:
    def test_changing_the_document_refreshes_plain_text(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)

        auth_client.patch(
            reverse("ideas:idea-detail", args=[idea.pk]),
            {"content": doc("متن جدید")},
            format="json",
        )

        idea.refresh_from_db()
        assert idea.plain_text == "متن جدید"

    def test_tags_can_be_replaced(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)

        response = auth_client.patch(
            reverse("ideas:idea-detail", args=[idea.pk]),
            {"tags": ["جدید"]},
            format="json",
        )

        assert response.json()["tags"] == ["جدید"]


class TestArchiveActions:
    def test_archive_moves_the_idea_out_of_circulation(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user, status=IdeaStatus.DOING)

        response = auth_client.post(reverse("ideas:idea-archive", args=[idea.pk]))

        assert response.status_code == 200
        idea.refresh_from_db()
        assert idea.status == IdeaStatus.ARCHIVED
        assert idea.is_archived is True

    def test_restore_returns_the_idea_to_the_idea_status(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user, status=IdeaStatus.ARCHIVED)

        response = auth_client.post(reverse("ideas:idea-restore", args=[idea.pk]))

        assert response.status_code == 200
        idea.refresh_from_db()
        assert idea.status == IdeaStatus.IDEA


class TestCategories:
    def test_colour_must_come_from_the_fixed_palette(self, auth_client: APIClient) -> None:
        response = auth_client.post(
            reverse("ideas:category-list"),
            {"name": "دستهٔ تازه", "color": "#123456"},
            format="json",
        )

        assert response.status_code == 400

    def test_duplicate_name_for_the_same_owner_is_rejected(
        self, auth_client: APIClient, user: User
    ) -> None:
        CategoryFactory(owner=user, name="وب‌سایت")

        response = auth_client.post(
            reverse("ideas:category-list"), {"name": "وب‌سایت"}, format="json"
        )

        assert response.status_code == 400

    def test_the_same_name_is_allowed_for_a_different_owner(
        self, auth_client: APIClient, user: User, other_user: User
    ) -> None:
        CategoryFactory(owner=other_user, name="وب‌سایت")

        response = auth_client.post(
            reverse("ideas:category-list"), {"name": "وب‌سایت"}, format="json"
        )

        assert response.status_code == 201

    def test_idea_count_is_reported(self, auth_client: APIClient, user: User) -> None:
        category = CategoryFactory(owner=user)
        IdeaFactory.create_batch(2, owner=user, category=category)

        row = auth_client.get(reverse("ideas:category-list")).json()["results"][0]

        assert row["idea_count"] == 2

    def test_deleting_a_category_keeps_its_ideas(self, auth_client: APIClient, user: User) -> None:
        category = CategoryFactory(owner=user)
        idea = IdeaFactory(owner=user, category=category)

        auth_client.delete(reverse("ideas:category-detail", args=[category.pk]))

        idea.refresh_from_db()
        assert idea.category is None
        assert Category.objects.filter(pk=category.pk).exists() is False
