"""The shared plumbing in core/.

Everything here is exercised indirectly by the feature tests, but only ever
along the happy path. These cover the shapes the frontend actually depends on
and the failure branches nothing else reaches.
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.models import User
from tests.factories import IdeaFactory

pytestmark = pytest.mark.django_db


class TestErrorShape:
    """Every error answers with the same three keys.

    DRF's own output mixes two shapes -- a bare field map for validation, a
    `detail` string for everything else -- which would need two code paths in
    the client.
    """

    def test_a_validation_error_carries_the_field_map(self, auth_client: APIClient) -> None:
        response = auth_client.post(reverse("ideas:idea-list"), {}, format="json")

        body = response.json()
        assert response.status_code == 400
        assert set(body) == {"detail", "code", "errors"}
        assert "title" in body["errors"]

    def test_the_detail_is_a_readable_sentence(self, auth_client: APIClient) -> None:
        """Not a list, and not a dict -- something that can be shown as-is."""
        response = auth_client.post(reverse("ideas:idea-list"), {}, format="json")

        assert isinstance(response.json()["detail"], str)
        assert response.json()["detail"]

    def test_a_missing_record_uses_the_same_shape(self, auth_client: APIClient) -> None:
        response = auth_client.get(reverse("ideas:idea-detail", args=[999999]))

        body = response.json()
        assert response.status_code == 404
        assert set(body) == {"detail", "code", "errors"}
        assert body["errors"] is None

    def test_a_refused_request_uses_the_same_shape(self, api_client: APIClient) -> None:
        body = api_client.get(reverse("ideas:idea-list")).json()

        assert set(body) == {"detail", "code", "errors"}

    def test_a_wrong_method_uses_the_same_shape(self, auth_client: APIClient) -> None:
        body = auth_client.put(reverse("ideas:idea-list"), {}, format="json").json()

        assert set(body) == {"detail", "code", "errors"}

    def test_the_message_is_persian(self, api_client: APIClient) -> None:
        detail = api_client.get(reverse("ideas:idea-list")).json()["detail"]

        # No Latin letters: the interface is Persian throughout.
        assert not any("a" <= char.lower() <= "z" for char in detail)


class TestPaginationEnvelope:
    def test_the_shape_the_client_reads(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory.create_batch(3, owner=user)

        body = auth_client.get(reverse("ideas:idea-list")).json()

        assert set(body) == {"results", "pagination"}
        assert set(body["pagination"]) == {
            "count",
            "page",
            "pages",
            "page_size",
            "next",
            "previous",
        }

    def test_paging_through_a_longer_list(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory.create_batch(5, owner=user)

        first = auth_client.get(reverse("ideas:idea-list"), {"page_size": 2}).json()

        assert len(first["results"]) == 2
        assert first["pagination"]["count"] == 5
        assert first["pagination"]["pages"] == 3
        assert first["pagination"]["next"] is not None
        assert first["pagination"]["previous"] is None

    def test_the_page_size_is_capped(self, auth_client: APIClient, user: User) -> None:
        """A client cannot ask for the whole table in one request."""
        response = auth_client.get(reverse("ideas:idea-list"), {"page_size": 100000})

        assert response.json()["pagination"]["page_size"] == 100

    def test_a_page_past_the_end_is_a_clean_404(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user)

        response = auth_client.get(reverse("ideas:idea-list"), {"page": 99})

        assert response.status_code == 404
        assert set(response.json()) == {"detail", "code", "errors"}


class TestHealthEndpoint:
    def test_it_reports_both_dependencies(self, api_client: APIClient) -> None:
        body = api_client.get(reverse("health")).json()

        assert body["status"] == "ok"
        assert body["database"] == "ok"
        assert body["cache"] == "ok"

    def test_the_cache_check_survives_a_backend_failure(self, monkeypatch) -> None:
        """Redis backs both the throttle and the reminder queue, so losing it
        means reminders have stopped even though the API still answers.

        The check is called directly: patching the cache underneath a live
        request would take the test client's own session store with it.
        """
        from core.views import HealthView

        def explode(*args, **kwargs):
            raise RuntimeError("Redis is gone")

        monkeypatch.setattr("core.views.cache.set", explode)

        assert HealthView()._check_cache() == "error"

    def test_the_cache_check_notices_a_value_that_does_not_come_back(self, monkeypatch) -> None:
        """A cache that accepts writes and forgets them is also broken."""
        from core.views import HealthView

        monkeypatch.setattr("core.views.cache.get", lambda *a, **k: None)

        assert HealthView()._check_cache() == "error"

    def test_the_database_check_survives_a_connection_failure(self, monkeypatch) -> None:
        from django.db import DatabaseError

        from core.views import HealthView

        def explode(*args, **kwargs):
            raise DatabaseError("connection refused")

        # Patched on the view's own reference, so Django's transaction
        # machinery keeps the real connection.
        monkeypatch.setattr("core.views.connection.cursor", explode)

        assert HealthView()._check_database() == "error"

    def test_a_failing_dependency_makes_the_whole_probe_unhealthy(
        self, api_client: APIClient, monkeypatch
    ) -> None:
        """Which is what the deployment's health check acts on."""
        from core.views import HealthView

        monkeypatch.setattr(HealthView, "_check_cache", lambda self: "error")

        response = api_client.get(reverse("health"))

        assert response.status_code == 503
        assert response.json()["status"] == "error"
        assert response.json()["cache"] == "error"
        assert response.json()["database"] == "ok"


class TestAbstractModelBases:
    def test_every_owned_model_actually_carries_an_owner(self) -> None:
        """The multi-user guarantee is structural: a model holding user data
        that forgot to inherit OwnedModel would be a silent leak."""
        from apps.ideas.models import Attachment, Category, Idea, Tag
        from apps.notifications.models import Notification
        from apps.reminders.models import Reminder

        for model in (Idea, Category, Tag, Attachment, Reminder, Notification):
            assert any(field.name == "owner" for field in model._meta.fields), (
                f"{model.__name__} has no owner"
            )

    def test_timestamps_are_maintained_without_being_asked(self, user: User) -> None:
        idea = IdeaFactory(owner=user)
        first = idea.updated_at

        idea.title = "عنوان تازه"
        idea.save(update_fields=["title", "updated_at"])
        idea.refresh_from_db()

        assert idea.updated_at > first
        assert idea.created_at < idea.updated_at
