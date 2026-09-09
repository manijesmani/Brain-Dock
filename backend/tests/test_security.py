"""Security properties, asserted rather than assumed.

Most of what is here was designed in from the start. These tests exist so that
a later change cannot quietly undo any of it -- a settings edit, a new view
that forgets a permission, a serializer that starts accepting a field it
should not.
"""

import pytest
from django.conf import settings
from django.test import Client, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.ideas.models import Attachment, Idea
from apps.users.models import User
from tests.factories import IdeaFactory, UserFactory
from tests.media_fixtures import image_upload

pytestmark = pytest.mark.django_db


class TestProductionSettings:
    """The values that only ever take effect on the server.

    Nothing else exercises this module, so without these tests a mistake in it
    would first be discovered in production.
    """

    @pytest.fixture
    def prod(self, monkeypatch):
        monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "braindock.example")
        monkeypatch.setenv("DJANGO_CSRF_TRUSTED_ORIGINS", "https://braindock.example")

        import importlib

        from config.settings import prod as module

        return importlib.reload(module)

    def test_debug_is_off(self, prod) -> None:
        assert prod.DEBUG is False

    def test_allowed_hosts_has_no_default(self, monkeypatch) -> None:
        """A fallback would mean trusting whatever Host header arrives."""
        import importlib

        from django.core.exceptions import ImproperlyConfigured

        monkeypatch.delenv("DJANGO_ALLOWED_HOSTS", raising=False)

        with pytest.raises(ImproperlyConfigured):
            importlib.reload(importlib.import_module("config.settings.prod"))

    def test_cookies_are_https_only(self, prod) -> None:
        assert prod.SESSION_COOKIE_SECURE is True
        assert prod.CSRF_COOKIE_SECURE is True

    def test_the_session_cookie_is_hidden_from_scripts(self, prod) -> None:
        assert prod.SESSION_COOKIE_HTTPONLY is True

    def test_the_csrf_cookie_is_readable_on_purpose(self, prod) -> None:
        """The SPA copies it into a header; HttpOnly would break every write."""
        assert prod.CSRF_COOKIE_HTTPONLY is False

    def test_http_is_redirected_and_hsts_is_long(self, prod) -> None:
        assert prod.SECURE_SSL_REDIRECT is True
        assert prod.SECURE_HSTS_SECONDS >= 60 * 60 * 24 * 365
        assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True

    def test_framing_is_refused(self, prod) -> None:
        assert prod.X_FRAME_OPTIONS == "DENY"

    def test_no_cross_origin_access_is_granted(self, prod) -> None:
        """In production the SPA is same-origin, so CORS has nothing to allow."""
        assert prod.CORS_ALLOWED_ORIGINS == []

    def test_media_root_is_still_unrouted(self, prod) -> None:
        from config import urls

        assert not any(
            str(getattr(pattern, "pattern", "")).startswith("media") for pattern in urls.urlpatterns
        )

    def test_exactly_one_proxy_is_trusted(self, prod) -> None:
        """Behind Nginx, REMOTE_ADDR is the proxy, so DRF reads X-Forwarded-For.

        The count has to match deploy/nginx, which puts exactly one proxy in
        front and overwrites the header rather than appending to it.
        """
        assert prod.REST_FRAMEWORK["NUM_PROXIES"] == 1


class TestThrottleIdentity:
    """Which address the rate limiter counts against.

    This is the difference between a login throttle that works and one that a
    caller can step around by writing its own X-Forwarded-For.
    """

    def _request_with_forged_header(self):
        from rest_framework.test import APIRequestFactory

        # The first address is what an attacker put there; the second is what
        # the trusted proxy appended.
        return APIRequestFactory().get("/api/ideas/", HTTP_X_FORWARDED_FOR="10.0.0.1, 203.0.113.9")

    def test_only_the_address_the_proxy_appended_is_counted(self) -> None:
        from rest_framework.throttling import BaseThrottle

        request = self._request_with_forged_header()

        with override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}):
            assert BaseThrottle().get_ident(request) == "203.0.113.9"

    def test_without_the_setting_the_whole_forged_chain_would_be_the_identity(self) -> None:
        """The failure this guards against, spelled out.

        With no proxy count configured, DRF uses the entire header. Anyone
        could then vary it per request and start every request in a fresh
        rate-limit bucket.
        """
        from rest_framework.throttling import BaseThrottle

        request = self._request_with_forged_header()

        with override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, "NUM_PROXIES": None}):
            assert BaseThrottle().get_ident(request) == "10.0.0.1,203.0.113.9"


class TestPasswordPolicy:
    def test_a_short_password_is_refused(self) -> None:
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            validate_password("short1234")

    def test_a_long_enough_password_is_accepted(self) -> None:
        from django.contrib.auth.password_validation import validate_password

        validate_password("correct-horse-battery-staple")


class TestCsrf:
    """DRF enforces CSRF for session authentication; this proves it is on."""

    def test_a_write_without_the_token_is_refused(self, user: User) -> None:
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)

        response = client.post(
            reverse("ideas:idea-list"),
            data='{"title": "بدون توکن"}',
            content_type="application/json",
        )

        assert response.status_code == 403
        assert Idea.objects.count() == 0

    def test_a_write_with_the_token_succeeds(self, user: User) -> None:
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        client.get(reverse("users:csrf"))
        token = client.cookies["csrftoken"].value

        response = client.post(
            reverse("ideas:idea-list"),
            data='{"title": "با توکن"}',
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        assert response.status_code == 201

    def test_reading_needs_no_token(self, user: User) -> None:
        """Safe methods are exempt, which is what lets the app load at all."""
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)

        assert client.get(reverse("ideas:idea-list")).status_code == 200


class TestSecurityHeaders:
    def test_the_api_forbids_every_kind_of_embedding(self, auth_client: APIClient) -> None:
        response = auth_client.get(reverse("ideas:idea-list"))

        policy = response["Content-Security-Policy"]
        assert "default-src 'none'" in policy
        assert "frame-ancestors 'none'" in policy

    def test_the_api_disclaims_device_permissions(self, auth_client: APIClient) -> None:
        response = auth_client.get(reverse("ideas:idea-list"))

        assert "camera=()" in response["Permissions-Policy"]
        assert "microphone=()" in response["Permissions-Policy"]

    def test_content_type_sniffing_is_off(self, auth_client: APIClient) -> None:
        response = auth_client.get(reverse("ideas:idea-list"))

        assert response["X-Content-Type-Options"] == "nosniff"

    def test_the_admin_keeps_its_own_policy(self, api_client: APIClient) -> None:
        """`default-src 'none'` would break the admin's own scripts."""
        response = api_client.get("/admin/login/")

        assert "Content-Security-Policy" not in response


class TestUnauthenticatedSurface:
    """Exactly three endpoints answer without a session, and no more."""

    @pytest.mark.parametrize(
        "route",
        [
            "ideas:idea-list",
            "ideas:category-list",
            "ideas:tag-list",
            "reminders:reminder-list",
            "notifications:notification-list",
            "users:me",
            "telegrambot:link",
        ],
    )
    def test_everything_else_refuses_an_anonymous_reader(
        self, api_client: APIClient, route: str
    ) -> None:
        assert api_client.get(reverse(route)).status_code == 403

    def test_health_is_open_by_design(self, api_client: APIClient) -> None:
        """The deployment probe runs before any session exists."""
        assert api_client.get(reverse("health")).status_code == 200

    def test_csrf_is_open_by_design(self, api_client: APIClient) -> None:
        """The SPA needs a token before it can log in."""
        assert api_client.get(reverse("users:csrf")).status_code == 200


class TestFieldsThatMustNotBeWritable:
    def test_ownership_cannot_be_reassigned(
        self, auth_client: APIClient, user: User, other_user: User
    ) -> None:
        """A serializer that accepted `owner` would hand records away."""
        idea = IdeaFactory(owner=user)

        auth_client.patch(
            reverse("ideas:idea-detail", args=[idea.pk]),
            {"owner": other_user.pk},
            format="json",
        )

        idea.refresh_from_db()
        assert idea.owner == user

    def test_staff_status_cannot_be_granted_through_the_profile(
        self, auth_client: APIClient, user: User
    ) -> None:
        auth_client.patch(
            reverse("users:me"),
            {"is_staff": True, "is_superuser": True},
            format="json",
        )

        user.refresh_from_db()
        assert user.is_staff is False
        assert user.is_superuser is False

    def test_the_telegram_chat_cannot_be_claimed_through_the_profile(
        self, auth_client: APIClient, user: User
    ) -> None:
        """Linking has to go through a one-time token, not a PATCH."""
        auth_client.patch(reverse("users:me"), {"telegram_chat_id": 12345}, format="json")

        user.refresh_from_db()
        assert user.telegram_chat_id is None

    def test_plain_text_cannot_be_forged(self, auth_client: APIClient) -> None:
        """It backs search, so a client-supplied value could poison results."""
        response = auth_client.post(
            reverse("ideas:idea-list"),
            {"title": "عنوان", "plain_text": "متن جعلی"},
            format="json",
        )

        assert Idea.objects.get(pk=response.json()["id"]).plain_text == ""


class TestStoredFilePaths:
    def test_a_hostile_filename_never_reaches_the_path(
        self, auth_client: APIClient, user: User
    ) -> None:
        """The name is replaced by a random one, so traversal has nothing to
        traverse."""
        idea = IdeaFactory(owner=user)

        auth_client.post(
            reverse("ideas:attachment-list"),
            {
                "idea": idea.pk,
                "kind": "image",
                "file": image_upload("../../../../etc/passwd.jpg"),
            },
            format="multipart",
        )

        attachment = Attachment.objects.get()
        assert ".." not in attachment.file.name
        assert attachment.file.name.startswith(f"attachments/{user.pk}/")

    def test_each_owner_gets_their_own_directory(
        self, api_client: APIClient, user: User, other_user: User
    ) -> None:
        for owner in (user, other_user):
            api_client.force_authenticate(user=owner)
            api_client.post(
                reverse("ideas:attachment-list"),
                {
                    "idea": IdeaFactory(owner=owner).pk,
                    "kind": "image",
                    "file": image_upload(),
                },
                format="multipart",
            )

        paths = dict(Attachment.objects.values_list("owner_id", "file"))
        assert paths[user.pk].startswith(f"attachments/{user.pk}/")
        assert paths[other_user.pk].startswith(f"attachments/{other_user.pk}/")


class TestAccountEnumeration:
    def test_login_says_the_same_thing_either_way(self, api_client: APIClient, user: User) -> None:
        """A different message for an unknown username would list the accounts."""
        url = reverse("users:login")

        unknown = api_client.post(
            url, {"username": "nobody-here", "password": "wrong"}, format="json"
        )
        known = api_client.post(
            url, {"username": user.username, "password": "wrong"}, format="json"
        )

        assert unknown.status_code == known.status_code
        assert unknown.json() == known.json()


class TestForeignRecordsAreInvisible:
    """A record belonging to somebody else answers 404, never 403.

    A 403 would confirm the record exists, which is itself a disclosure.
    """

    def test_an_idea(self, auth_client: APIClient, other_user: User) -> None:
        foreign = IdeaFactory(owner=other_user)

        assert auth_client.get(reverse("ideas:idea-detail", args=[foreign.pk])).status_code == 404

    def test_an_attachment_file(self, api_client: APIClient, user: User, other_user: User) -> None:
        api_client.force_authenticate(user=other_user)
        created = api_client.post(
            reverse("ideas:attachment-list"),
            {
                "idea": IdeaFactory(owner=other_user).pk,
                "kind": "image",
                "file": image_upload(),
            },
            format="multipart",
        ).json()

        api_client.force_authenticate(user=user)
        assert api_client.get(created["file_url"]).status_code == 404

    def test_a_reminder(self, auth_client: APIClient, other_user: User) -> None:
        from apps.reminders import services
        from apps.reminders.models import ReminderRecurrence

        foreign = services.set_reminder(
            idea=IdeaFactory(owner=other_user),
            recurrence=ReminderRecurrence.DAILY,
            hour=9,
            minute=0,
        )

        assert (
            auth_client.get(reverse("reminders:reminder-detail", args=[foreign.pk])).status_code
            == 404
        )


class TestSessionIsolation:
    def test_logging_out_ends_access(self, api_client: APIClient) -> None:
        from tests.factories import DEFAULT_PASSWORD

        user = UserFactory()
        api_client.post(
            reverse("users:login"),
            {"username": user.username, "password": DEFAULT_PASSWORD},
            format="json",
        )
        assert api_client.get(reverse("users:me")).status_code == 200

        api_client.post(reverse("users:logout"))

        assert api_client.get(reverse("users:me")).status_code == 403
