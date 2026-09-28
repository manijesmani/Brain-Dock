"""«دستگاه‌های فعال»: the browsers signed in to an account, and signing them out.

Every test signs in through the real login endpoint, so each client is a
browser with a session of its own, as it would be in use.
"""

import importlib
from datetime import timedelta

import pytest
from django.apps import apps as django_apps
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users import services
from apps.users.devices import SEEN_KEY, client_ip, describe_user_agent
from apps.users.models import DeviceSession, User
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
ANDROID = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
)
WINDOWS_EDGE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0"
)


@pytest.fixture(autouse=True)
def clear_throttle_cache() -> None:
    cache.clear()


def browser(user: User, *, agent: str = IPHONE, ip: str = "5.160.10.20") -> APIClient:
    """A client signed in through the login endpoint, as a browser would be."""
    client = APIClient(HTTP_USER_AGENT=agent, REMOTE_ADDR=ip)
    response = client.post(
        reverse("users:login"),
        {"username": user.username, "password": DEFAULT_PASSWORD},
        format="json",
    )
    assert response.status_code == 200
    return client


def listed(client: APIClient) -> list[dict]:
    response = client.get(reverse("users:device-list"))
    assert response.status_code == 200
    return response.json()


class TestNamingADevice:
    @pytest.mark.parametrize(
        ("agent", "name", "kind"),
        [
            (IPHONE, "Safari روی iPhone", "mobile"),
            (ANDROID, "Chrome روی Android", "mobile"),
            (WINDOWS_EDGE, "Edge روی Windows", "desktop"),
            (
                "Mozilla/5.0 (Linux; Android 13; SM-X700) AppleWebKit/537.36 (KHTML, like Gecko) "
                "SamsungBrowser/24.0 Chrome/115.0.0.0 Safari/537.36",
                "Samsung Internet روی Android",
                "tablet",
            ),
            (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:127.0) Gecko/20100101 "
                "Firefox/127.0",
                "Firefox روی macOS",
                "desktop",
            ),
            (
                "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
                "(KHTML, like Gecko) CriOS/126.0 Mobile/15E148 Safari/604.1",
                "Chrome روی iPad",
                "tablet",
            ),
            ("curl/8.5.0", "دستگاه ناشناخته", "unknown"),
            ("", "دستگاه نامشخص", "unknown"),
        ],
    )
    def test_names_read_in_persian(self, agent: str, name: str, kind: str) -> None:
        description = describe_user_agent(agent)

        assert (description.name, description.kind) == (name, kind)


class TestTheAddress:
    def test_without_a_proxy_the_forwarded_header_is_ignored(self, settings) -> None:
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": None}
        request = RequestFactory().get(
            "/", REMOTE_ADDR="5.160.10.20", HTTP_X_FORWARDED_FOR="1.1.1.1"
        )

        assert client_ip(request) == "5.160.10.20"

    def test_behind_the_proxy_the_address_it_forwarded_is_used(self, settings) -> None:
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
        request = RequestFactory().get(
            "/", REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="9.9.9.9, 91.98.0.7"
        )

        assert client_ip(request) == "91.98.0.7"

    def test_something_that_is_not_an_address_is_not_kept(self) -> None:
        request = RequestFactory().get("/", REMOTE_ADDR="not-an-address")

        assert client_ip(request) is None


class TestRecording:
    def test_signing_in_records_the_device(self) -> None:
        user = UserFactory()
        client = browser(user, agent=ANDROID, ip="5.160.10.20")

        devices = listed(client)

        assert len(devices) == 1
        device = devices[0]
        assert device["name"] == "Chrome روی Android"
        assert device["kind"] == "mobile"
        assert device["ip_address"] == "5.160.10.20"
        assert device["signed_in_at"] is not None
        assert device["current"] is True

    def test_every_browser_is_listed_this_one_first(self) -> None:
        user = UserFactory()
        browser(user, agent=IPHONE)
        browser(user, agent=WINDOWS_EDGE)
        phone = browser(user, agent=ANDROID)

        devices = listed(phone)

        assert devices[0]["name"] == "Chrome روی Android"
        assert [device["current"] for device in devices] == [True, False, False]
        assert {device["name"] for device in devices} == {
            "Chrome روی Android",
            "Safari روی iPhone",
            "Edge روی Windows",
        }

    def test_last_use_is_written_every_few_minutes_not_every_request(self) -> None:
        user = UserFactory()
        client = browser(user)
        device = DeviceSession.objects.get()
        first = device.last_seen_at

        client.get(reverse("users:me"))
        device.refresh_from_db()
        assert device.last_seen_at == first

        # Pretend the last write was ten minutes ago.
        session = Session.objects.get(pk=device.session_id)
        store = session.get_decoded()
        store[SEEN_KEY]["at"] = (timezone.now() - timedelta(minutes=10)).isoformat()
        Session.objects.save(session.pk, store, session.expire_date)

        client.get(reverse("users:me"))
        device.refresh_from_db()
        assert device.last_seen_at > first

    def test_a_session_from_before_is_recorded_on_its_next_request(self) -> None:
        user = UserFactory()
        client = APIClient(HTTP_USER_AGENT=IPHONE)
        client.force_login(user)
        assert not DeviceSession.objects.exists()

        client.get(reverse("users:me"))

        assert DeviceSession.objects.get().user == user

    def test_signing_out_removes_it(self) -> None:
        user = UserFactory()
        client = browser(user)

        client.post(reverse("users:logout"))

        assert not DeviceSession.objects.exists()

    def test_guests_are_not_recorded(self) -> None:
        client = APIClient(HTTP_USER_AGENT=IPHONE)
        client.post(reverse("users:guest"))
        client.get(reverse("users:me"))

        assert not DeviceSession.objects.exists()

    def test_signing_up_from_a_guest_records_the_account(self) -> None:
        client = APIClient(HTTP_USER_AGENT=IPHONE)
        client.post(reverse("users:guest"))

        client.post(
            reverse("users:signup"),
            {"first_name": "سارا", "username": "sara", "password": "quiet-harbour-lantern-47"},
            format="json",
        )

        assert listed(client)[0]["name"] == "Safari روی iPhone"

    def test_signing_in_from_a_guest_session_records_the_account(self) -> None:
        user = UserFactory()
        client = APIClient(HTTP_USER_AGENT=ANDROID)
        client.post(reverse("users:guest"))

        client.post(
            reverse("users:login"),
            {"username": user.username, "password": DEFAULT_PASSWORD},
            format="json",
        )

        assert DeviceSession.objects.get().user == user
        assert listed(client)[0]["current"] is True


class TestSigningOut:
    def test_another_device_is_signed_out(self) -> None:
        user = UserFactory()
        phone = browser(user, agent=IPHONE)
        laptop = browser(user, agent=WINDOWS_EDGE)
        target = next(device for device in listed(laptop) if not device["current"])

        response = laptop.delete(reverse("users:device-detail", args=[target["id"]]))

        assert response.status_code == 204
        assert phone.get(reverse("users:me")).status_code == 403
        assert laptop.get(reverse("users:me")).status_code == 200
        assert [device["name"] for device in listed(laptop)] == ["Edge روی Windows"]

    def test_this_device_signs_out_with_the_ordinary_button(self) -> None:
        user = UserFactory()
        client = browser(user)
        current = listed(client)[0]

        response = client.delete(reverse("users:device-detail", args=[current["id"]]))

        assert response.status_code == 400
        assert "خروج" in response.json()["detail"]
        assert client.get(reverse("users:me")).status_code == 200

    def test_another_accounts_device_is_not_found(self) -> None:
        mine = browser(UserFactory())
        theirs = browser(UserFactory())
        foreign = listed(theirs)[0]

        response = mine.delete(reverse("users:device-detail", args=[foreign["id"]]))

        assert response.status_code == 404
        assert theirs.get(reverse("users:me")).status_code == 200

    def test_every_other_device_at_once(self) -> None:
        user = UserFactory()
        others = [browser(user, agent=IPHONE), browser(user, agent=ANDROID)]
        # A session that never made a request, so it was never listed.
        unlisted = APIClient()
        unlisted.force_login(user)
        someone_else = browser(UserFactory())
        this = browser(user, agent=WINDOWS_EDGE)

        response = this.post(reverse("users:device-sign-out-others"))

        assert response.json() == {"signed_out": 3}
        for client in [*others, unlisted]:
            assert client.get(reverse("users:me")).status_code == 403
        assert this.get(reverse("users:me")).status_code == 200
        assert someone_else.get(reverse("users:me")).status_code == 200
        assert len(listed(this)) == 1

    def test_a_password_change_leaves_the_others_off_the_list(self) -> None:
        user = UserFactory()
        browser(user, agent=IPHONE)
        user.set_password("a-brand-new-password-for-this")
        user.save()
        client = APIClient(HTTP_USER_AGENT=ANDROID)
        client.post(
            reverse("users:login"),
            {"username": user.username, "password": "a-brand-new-password-for-this"},
            format="json",
        )

        devices = listed(client)

        assert [device["name"] for device in devices] == ["Chrome روی Android"]
        # The dead session is cleared away rather than left to be listed again.
        assert DeviceSession.objects.count() == 1


class TestWhoMayUseIt:
    def test_a_guest_gets_a_403(self) -> None:
        client = APIClient()
        client.post(reverse("users:guest"))

        response = client.get(reverse("users:device-list"))

        assert response.status_code == 403
        assert "مهمان" in response.json()["detail"]

    def test_anonymous_visitors_get_a_403(self, api_client: APIClient) -> None:
        assert api_client.get(reverse("users:device-list")).status_code == 403
        assert api_client.post(reverse("users:device-sign-out-others")).status_code == 403

    @pytest.mark.parametrize("kind", ["regular", "special", "owner"])
    def test_every_kind_of_account_has_it(self, kind: str) -> None:
        user = UserFactory(is_premium=kind == "special", is_superuser=kind == "owner")

        assert len(listed(browser(user))) == 1


class TestSessionsFromBeforeTheList:
    def test_the_migration_lists_signed_in_accounts_but_not_guests(self) -> None:
        user = UserFactory()
        signed_in = APIClient()
        signed_in.force_login(user)
        guest = services.create_guest()
        APIClient().force_login(guest)
        assert not DeviceSession.objects.exists()

        migration = importlib.import_module("apps.users.migrations.0005_record_signed_in_sessions")
        migration.record_signed_in_sessions(django_apps, None)

        device = DeviceSession.objects.get()
        assert device.user == user
        assert device.user_agent == ""
        assert device.signed_in_at is None
        assert describe_user_agent(device.user_agent).name == "دستگاه نامشخص"
