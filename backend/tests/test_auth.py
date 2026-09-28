import pytest
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_throttle_cache() -> None:
    """Throttle counters live in the cache and would leak between tests."""
    cache.clear()


class TestLogin:
    def test_valid_credentials_start_a_session(
        self, api_client: APIClient, user: User, password: str
    ) -> None:
        response = api_client.post(
            reverse("users:login"),
            {"username": user.username, "password": password},
            format="json",
        )

        assert response.status_code == 200
        assert response.json()["username"] == user.username
        assert "_auth_user_id" in api_client.session

    def test_wrong_password_is_rejected(self, api_client: APIClient, user: User) -> None:
        response = api_client.post(
            reverse("users:login"),
            {"username": user.username, "password": "wrong"},
            format="json",
        )

        assert response.status_code == 401
        assert "_auth_user_id" not in api_client.session

    def test_unknown_user_gives_the_same_message_as_a_wrong_password(
        self, api_client: APIClient, user: User
    ) -> None:
        """The endpoint must not reveal which accounts exist."""
        unknown = api_client.post(
            reverse("users:login"),
            {"username": "nobody", "password": "wrong"},
            format="json",
        )
        known = api_client.post(
            reverse("users:login"),
            {"username": user.username, "password": "wrong"},
            format="json",
        )

        assert unknown.status_code == known.status_code == 401
        assert unknown.json()["detail"] == known.json()["detail"]

    def test_repeated_attempts_are_throttled(self, api_client: APIClient) -> None:
        url = reverse("users:login")
        payload = {"username": "nobody", "password": "wrong"}

        statuses = [api_client.post(url, payload, format="json").status_code for _ in range(12)]

        assert 429 in statuses


class TestCurrentUser:
    def test_requires_authentication(self, api_client: APIClient) -> None:
        assert api_client.get(reverse("users:me")).status_code == 403

    def test_returns_the_signed_in_user(self, auth_client: APIClient, user: User) -> None:
        response = auth_client.get(reverse("users:me"))

        assert response.status_code == 200
        body = response.json()
        assert body["username"] == user.username
        assert body["stale_after_days"] == 14
        assert body["is_telegram_linked"] is False

    def test_display_name_falls_back_to_the_username(
        self, auth_client: APIClient, user: User
    ) -> None:
        user.first_name = ""
        user.save(update_fields=["first_name"])

        assert auth_client.get(reverse("users:me")).json()["display_name"] == user.username

    def test_stale_threshold_can_be_changed(self, auth_client: APIClient, user: User) -> None:
        response = auth_client.patch(reverse("users:me"), {"stale_after_days": 30}, format="json")

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.stale_after_days == 30

    @pytest.mark.parametrize("value", [0, 91, -1])
    def test_stale_threshold_outside_the_allowed_range_is_rejected(
        self, auth_client: APIClient, value: int
    ) -> None:
        response = auth_client.patch(
            reverse("users:me"), {"stale_after_days": value}, format="json"
        )

        assert response.status_code == 400

    def test_username_cannot_be_changed(self, auth_client: APIClient, user: User) -> None:
        auth_client.patch(reverse("users:me"), {"username": "hacker"}, format="json")

        user.refresh_from_db()
        assert user.username != "hacker"


class TestLogout:
    def test_ends_the_session(self, api_client: APIClient, user: User, password: str) -> None:
        api_client.post(
            reverse("users:login"),
            {"username": user.username, "password": password},
            format="json",
        )

        response = api_client.post(reverse("users:logout"))

        assert response.status_code == 204
        assert "_auth_user_id" not in api_client.session


class TestCsrf:
    def test_sets_the_csrf_cookie(self, api_client: APIClient) -> None:
        response = api_client.get(reverse("users:csrf"))

        assert response.status_code == 200
        assert settings.CSRF_COOKIE_NAME in response.cookies
