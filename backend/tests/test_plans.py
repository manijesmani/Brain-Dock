"""What each kind of account may do, and how a visitor becomes one.

The rules themselves are in apps.users.plans: guests and free accounts hold at
most FREE_IDEA_LIMIT ideas and attach nothing, premium lifts both limits, and
the Telegram bot is the site owner's alone.
"""

from datetime import timedelta

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ideas.models import Attachment, AttachmentKind, Idea, IdeaStatus
from apps.ideas.services import create_attachment, create_idea
from apps.notifications.channels.telegram import TelegramChannel
from apps.telegrambot import handlers, messages
from apps.telegrambot.models import TelegramLinkToken
from apps.users import plans, services
from apps.users.models import User
from tests.factories import DEFAULT_PASSWORD, IdeaFactory, UserFactory
from tests.media_fixtures import image_upload

pytestmark = pytest.mark.django_db

# Long and unusual enough for every password validator.
NEW_PASSWORD = "quiet-harbour-lantern-47"


@pytest.fixture(autouse=True)
def clear_throttle_cache() -> None:
    """Throttle counters live in the cache and would leak between tests."""
    cache.clear()


@pytest.fixture
def guest() -> User:
    return services.create_guest()


@pytest.fixture
def free_user() -> User:
    return UserFactory(is_premium=False)


@pytest.fixture
def premium_user() -> User:
    return UserFactory(is_premium=True)


@pytest.fixture
def site_owner() -> User:
    return UserFactory(is_premium=False, is_superuser=True)


def client_for(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def add_idea(client: APIClient, title: str = "ایدهٔ تازه"):
    return client.post(reverse("ideas:idea-list"), {"title": title}, format="json")


def attach_image(client: APIClient, idea: Idea):
    return client.post(
        reverse("ideas:attachment-list"),
        {"idea": idea.pk, "kind": AttachmentKind.IMAGE, "file": image_upload()},
        format="multipart",
    )


class TestGuestSession:
    def test_a_visitor_without_a_session_gets_a_guest_account(self, api_client: APIClient) -> None:
        response = api_client.post(reverse("users:guest"))

        assert response.status_code == 201
        body = response.json()
        assert body["plan"] == "guest"
        assert body["display_name"] == "مهمان"

        guest = User.objects.get()
        assert guest.is_guest is True
        assert guest.has_usable_password() is False
        assert api_client.get(reverse("users:me")).status_code == 200

    def test_a_signed_in_visitor_is_not_given_a_second_account(self, api_client: APIClient) -> None:
        api_client.post(reverse("users:guest"))

        again = api_client.post(reverse("users:guest"))

        assert again.status_code == 200
        assert User.objects.count() == 1

    def test_nobody_can_sign_into_a_guest_with_a_password(
        self, api_client: APIClient, guest: User
    ) -> None:
        response = api_client.post(
            reverse("users:login"),
            {"username": guest.username, "password": "anything-at-all"},
            format="json",
        )

        assert response.status_code == 401

    def test_starting_guest_sessions_is_rate_limited(self) -> None:
        """A script must not be able to fill the user table."""
        statuses = [APIClient().post(reverse("users:guest")).status_code for _ in range(35)]

        assert 429 in statuses

    def test_a_guest_uses_the_app_like_anyone_else(self, guest: User) -> None:
        client = client_for(guest)

        assert add_idea(client).status_code == 201
        assert (
            client.post(
                reverse("ideas:category-list"), {"name": "کار", "color": "#3B82F6"}, format="json"
            ).status_code
            == 201
        )


class TestTheAccountTellsTheClientItsPlan:
    @pytest.mark.parametrize(
        ("account", "plan", "limit", "media", "owner_only"),
        [
            ("guest", "guest", 2, False, False),
            ("free_user", "free", 2, False, False),
            ("premium_user", "premium", None, True, False),
            ("site_owner", "owner", None, True, True),
        ],
    )
    def test_each_plan(
        self, request, account: str, plan: str, limit, media: bool, owner_only: bool
    ) -> None:
        body = client_for(request.getfixturevalue(account)).get(reverse("users:me")).json()

        assert body["plan"] == plan
        assert body["idea_limit"] == limit
        assert body["can_attach_media"] is media
        assert body["can_use_telegram"] is owner_only
        assert body["can_manage_users"] is owner_only

    def test_the_count_includes_archived_ideas(self, free_user: User) -> None:
        IdeaFactory(owner=free_user)
        IdeaFactory(owner=free_user, status=IdeaStatus.ARCHIVED)

        assert client_for(free_user).get(reverse("users:me")).json()["idea_count"] == 2


class TestIdeaLimit:
    @pytest.mark.parametrize("account", ["guest", "free_user"])
    def test_two_ideas_and_no_more(self, request, account: str) -> None:
        user = request.getfixturevalue(account)
        client = client_for(user)

        assert add_idea(client, "یک").status_code == 201
        assert add_idea(client, "دو").status_code == 201
        third = add_idea(client, "سه")

        assert third.status_code == 403
        assert third.json()["code"] == "idea_limit_reached"
        assert "۲" in third.json()["detail"]
        assert Idea.objects.filter(owner=user).count() == 2

    def test_archived_ideas_still_count(self, free_user: User) -> None:
        """Archiving is a status, not a way around the limit."""
        IdeaFactory(owner=free_user)
        IdeaFactory(owner=free_user, status=IdeaStatus.ARCHIVED)

        assert add_idea(client_for(free_user)).status_code == 403

    def test_deleting_an_idea_frees_its_place(self, free_user: User) -> None:
        first = IdeaFactory(owner=free_user)
        IdeaFactory(owner=free_user)
        client = client_for(free_user)

        client.delete(reverse("ideas:idea-detail", args=[first.pk]))

        assert add_idea(client).status_code == 201

    def test_the_limit_is_a_setting(self, settings, free_user: User) -> None:
        settings.FREE_IDEA_LIMIT = 3
        client = client_for(free_user)

        assert [add_idea(client).status_code for _ in range(4)] == [201, 201, 201, 403]

    @pytest.mark.parametrize("account", ["premium_user", "site_owner"])
    def test_premium_and_the_owner_have_no_limit(self, request, account: str) -> None:
        client = client_for(request.getfixturevalue(account))

        assert all(add_idea(client).status_code == 201 for _ in range(5))

    def test_the_service_enforces_it_for_every_caller(self, free_user: User) -> None:
        IdeaFactory(owner=free_user)
        IdeaFactory(owner=free_user)

        with pytest.raises(plans.IdeaLimitReached):
            create_idea(owner=free_user, title="سومی")


class TestMedia:
    @pytest.mark.parametrize("account", ["guest", "free_user"])
    def test_attaching_needs_premium(self, request, account: str) -> None:
        user = request.getfixturevalue(account)
        idea = IdeaFactory(owner=user)

        response = attach_image(client_for(user), idea)

        assert response.status_code == 403
        assert response.json()["code"] == "premium_required"
        assert Attachment.objects.count() == 0

    @pytest.mark.parametrize("account", ["premium_user", "site_owner"])
    def test_premium_and_the_owner_can_attach(self, request, account: str) -> None:
        user = request.getfixturevalue(account)

        assert attach_image(client_for(user), IdeaFactory(owner=user)).status_code == 201

    def test_the_service_refuses_too(self, free_user: User) -> None:
        with pytest.raises(plans.PremiumRequired):
            create_attachment(
                idea=IdeaFactory(owner=free_user), upload=image_upload(), kind=AttachmentKind.IMAGE
            )

    def test_what_was_attached_stays_after_premium_ends(self, premium_user: User) -> None:
        client = client_for(premium_user)
        attach_image(client, IdeaFactory(owner=premium_user))
        attachment = Attachment.objects.get()

        premium_user.is_premium = False
        premium_user.save(update_fields=["is_premium"])

        assert client.get(reverse("ideas:attachment-file", args=[attachment.pk])).status_code == 200
        assert (
            client.delete(reverse("ideas:attachment-detail", args=[attachment.pk])).status_code
            == 204
        )

    def test_a_guest_cannot_set_a_profile_picture(self, guest: User) -> None:
        response = client_for(guest).post(
            reverse("users:avatar"), {"file": image_upload()}, format="multipart"
        )

        assert response.status_code == 403

    def test_a_free_account_can(self, free_user: User) -> None:
        response = client_for(free_user).post(
            reverse("users:avatar"), {"file": image_upload()}, format="multipart"
        )

        assert response.status_code == 200


class TestTelegramIsTheOwnersAlone:
    @pytest.mark.parametrize("account", ["guest", "free_user", "premium_user"])
    def test_everyone_else_is_refused_the_link_section(self, request, account: str) -> None:
        client = client_for(request.getfixturevalue(account))

        assert client.get(reverse("telegrambot:link")).status_code == 403
        assert client.post(reverse("telegrambot:link")).status_code == 403
        assert TelegramLinkToken.objects.count() == 0

    def test_the_owner_gets_it(self, site_owner: User) -> None:
        assert client_for(site_owner).get(reverse("telegrambot:link")).status_code == 200

    def test_a_link_issued_to_anyone_else_is_not_honoured(self, premium_user: User) -> None:
        """A token issued before the bot became the owner's alone."""
        token = TelegramLinkToken.objects.create(
            user=premium_user, expires_at=timezone.now() + timedelta(minutes=10)
        )

        result = handlers.link_account(chat_id=555, token=token.token)

        premium_user.refresh_from_db()
        assert result == messages.LINK_INVALID
        assert premium_user.telegram_chat_id is None

    def test_a_chat_linked_to_anyone_else_is_not_served(self, premium_user: User) -> None:
        premium_user.telegram_chat_id = 555
        premium_user.save(update_fields=["telegram_chat_id"])

        assert TelegramChannel().is_available_for(premium_user) is False

    def test_the_owners_linked_chat_is(self, site_owner: User) -> None:
        site_owner.telegram_chat_id = 555
        site_owner.save(update_fields=["telegram_chat_id"])

        assert TelegramChannel().is_available_for(site_owner) is True


class TestSignup:
    def test_a_guest_becomes_an_account_and_keeps_its_ideas(self, api_client: APIClient) -> None:
        api_client.post(reverse("users:guest"))
        add_idea(api_client, "از زمان مهمانی")
        guest_id = User.objects.get().pk

        response = api_client.post(
            reverse("users:signup"),
            {"first_name": "سارا", "username": "sara", "password": NEW_PASSWORD},
            format="json",
        )

        assert response.status_code == 201
        assert response.json()["plan"] == "free"
        account = User.objects.get()
        assert account.pk == guest_id
        assert account.username == "sara"
        assert account.is_guest is False
        assert Idea.objects.get().owner == account
        # Still signed in, now as the account.
        assert api_client.get(reverse("users:me")).json()["username"] == "sara"

    def test_the_new_password_signs_in(self, api_client: APIClient) -> None:
        api_client.post(reverse("users:guest"))
        api_client.post(
            reverse("users:signup"),
            {"first_name": "سارا", "username": "sara", "password": NEW_PASSWORD},
            format="json",
        )
        api_client.post(reverse("users:logout"))

        response = api_client.post(
            reverse("users:login"), {"username": "sara", "password": NEW_PASSWORD}, format="json"
        )

        assert response.status_code == 200

    def test_a_visitor_without_a_session_can_sign_up_directly(self, api_client: APIClient) -> None:
        response = api_client.post(
            reverse("users:signup"),
            {"first_name": "سارا", "username": "sara", "password": NEW_PASSWORD},
            format="json",
        )

        assert response.status_code == 201
        assert User.objects.get().is_guest is False
        assert api_client.get(reverse("users:me")).status_code == 200

    def test_an_account_cannot_sign_up_again(self, free_user: User) -> None:
        response = client_for(free_user).post(
            reverse("users:signup"),
            {"first_name": "سارا", "username": "another", "password": NEW_PASSWORD},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["code"] == "already_signed_up"
        assert User.objects.count() == 1

    def test_a_taken_name_is_refused_whatever_its_case(
        self, api_client: APIClient, free_user: User
    ) -> None:
        response = api_client.post(
            reverse("users:signup"),
            {
                "first_name": "سارا",
                "username": free_user.username.upper(),
                "password": NEW_PASSWORD,
            },
            format="json",
        )

        assert response.status_code == 400
        assert "username" in response.json()["errors"]

    @pytest.mark.parametrize("username", ["guest-1234", "Guest-me", "با فاصله", "a/b"])
    def test_names_that_are_not_allowed(self, api_client: APIClient, username: str) -> None:
        response = api_client.post(
            reverse("users:signup"),
            {"first_name": "سارا", "username": username, "password": NEW_PASSWORD},
            format="json",
        )

        assert response.status_code == 400
        assert "username" in response.json()["errors"]

    # Too short, only digits, and too close to the name.
    @pytest.mark.parametrize("password", ["short", "123456789012345", "saraahmadi12"])
    def test_a_weak_password_is_refused(self, api_client: APIClient, password: str) -> None:
        response = api_client.post(
            reverse("users:signup"),
            {"first_name": "سارا", "username": "saraahmadi", "password": password},
            format="json",
        )

        assert response.status_code == 400
        assert "password" in response.json()["errors"]
        assert User.objects.count() == 0

    def test_the_reason_is_given_in_persian(self, api_client: APIClient) -> None:
        """Django's own catalogue would answer a short password in English."""
        response = api_client.post(
            reverse("users:signup"),
            {"first_name": "سارا", "username": "sara", "password": "short"},
            format="json",
        )

        assert response.json()["detail"] == "رمز عبور باید دست‌کم ۱۲ حرف باشد."

    def test_signing_up_is_rate_limited(self, api_client: APIClient) -> None:
        url = reverse("users:signup")
        statuses = [
            api_client.post(
                url, {"first_name": "سارا", "username": "x", "password": "y"}, format="json"
            ).status_code
            for _ in range(25)
        ]

        assert 429 in statuses


class TestSigningInFromAGuestSession:
    def test_logging_in_switches_to_the_account(
        self, api_client: APIClient, free_user: User
    ) -> None:
        api_client.post(reverse("users:guest"))

        api_client.post(
            reverse("users:login"),
            {"username": free_user.username, "password": DEFAULT_PASSWORD},
            format="json",
        )

        assert api_client.get(reverse("users:me")).json()["username"] == free_user.username


class TestSigningInNeedsTheCsrfToken:
    """Otherwise another site could sign a visitor into an account it controls."""

    @pytest.mark.parametrize("route", ["users:guest", "users:signup", "users:login"])
    def test_without_the_token_nothing_happens(self, route: str, free_user: User) -> None:
        client = Client(enforce_csrf_checks=True)

        response = client.post(
            reverse(route),
            data=f'{{"username": "{free_user.username}", "password": "{DEFAULT_PASSWORD}"}}',
            content_type="application/json",
        )

        assert response.status_code == 403
        assert User.objects.count() == 1
        assert "_auth_user_id" not in client.session

    def test_with_the_token_a_guest_session_starts(self) -> None:
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("users:csrf"))
        token = client.cookies[settings.CSRF_COOKIE_NAME].value

        response = client.post(reverse("users:guest"), HTTP_X_CSRFTOKEN=token)

        assert response.status_code == 201


class TestSignupTakesAName:
    def test_the_name_is_required(self, api_client: APIClient) -> None:
        response = api_client.post(
            reverse("users:signup"), {"username": "sara", "password": NEW_PASSWORD}, format="json"
        )

        assert response.status_code == 400
        assert "first_name" in response.json()["errors"]
        assert response.json()["detail"] == "نام را بنویس."

    def test_the_name_is_what_the_app_calls_them(self, api_client: APIClient) -> None:
        response = api_client.post(
            reverse("users:signup"),
            {"first_name": "سارا", "username": "sara", "password": NEW_PASSWORD},
            format="json",
        )

        assert response.json()["display_name"] == "سارا"


class TestNothingIsDeletedAutomatically:
    """Every idea, a guest's included, stays in the database for good."""

    def test_no_scheduled_job_deletes_anything(self, settings) -> None:
        scheduled = {entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()}

        assert scheduled == {"reminders.dispatch_due", "notifications.send_stale_digests"}

    def test_a_guest_left_behind_keeps_its_ideas(
        self, api_client: APIClient, free_user: User
    ) -> None:
        api_client.post(reverse("users:guest"))
        add_idea(api_client, "از زمان مهمانی")

        api_client.post(
            reverse("users:login"),
            {"username": free_user.username, "password": DEFAULT_PASSWORD},
            format="json",
        )

        assert Idea.objects.filter(title="از زمان مهمانی", owner__is_guest=True).exists()

    def test_a_guest_session_lasts_far_longer_than_an_accounts(
        self, api_client: APIClient, settings
    ) -> None:
        """The cookie is a guest's only way back to its ideas."""
        api_client.post(reverse("users:guest"))

        assert api_client.session.get_expiry_age() == settings.GUEST_SESSION_AGE

    def test_signing_up_starts_an_ordinary_session(self, api_client: APIClient, settings) -> None:
        api_client.post(reverse("users:guest"))
        api_client.post(
            reverse("users:signup"),
            {"first_name": "سارا", "username": "sara", "password": NEW_PASSWORD},
            format="json",
        )

        assert api_client.session.get_expiry_age() == settings.SESSION_COOKIE_AGE


def special_form(username: str = "ali", **extra: object) -> dict:
    return {"first_name": "علی", "username": username, "password": NEW_PASSWORD, **extra}


class TestUserPanel:
    """The owner's panel: the accounts, and the special ones made there."""

    @pytest.mark.parametrize("account", ["guest", "free_user", "premium_user"])
    def test_everyone_but_the_owner_is_refused(self, request, account: str) -> None:
        client = client_for(request.getfixturevalue(account))

        assert client.get(reverse("panel:user-list")).status_code == 403
        assert (
            client.post(reverse("panel:user-list"), special_form(), format="json").status_code
            == 403
        )
        assert not User.objects.filter(username="ali").exists()

    def test_anonymous_visitors_are_refused(self, api_client: APIClient) -> None:
        assert api_client.get(reverse("panel:user-list")).status_code == 403

    def test_the_owner_sees_the_accounts_but_not_guests_or_itself(
        self, site_owner: User, free_user: User, premium_user: User, guest: User
    ) -> None:
        IdeaFactory(owner=free_user)

        rows = client_for(site_owner).get(reverse("panel:user-list")).json()["results"]

        by_name = {row["username"]: row for row in rows}
        assert set(by_name) == {free_user.username, premium_user.username}
        assert by_name[free_user.username]["plan"] == "free"
        assert by_name[free_user.username]["idea_count"] == 1
        assert by_name[premium_user.username]["plan"] == "premium"

    def test_the_owner_makes_a_special_account(
        self, site_owner: User, api_client: APIClient
    ) -> None:
        response = client_for(site_owner).post(
            reverse("panel:user-list"), special_form(), format="json"
        )

        assert response.status_code == 201
        assert response.json()["plan"] == "premium"
        made = User.objects.get(username="ali")
        assert made.first_name == "علی"
        assert made.is_premium is True
        # Kept as a hash, never as typed.
        assert made.password != NEW_PASSWORD
        assert made.check_password(NEW_PASSWORD)

        signed_in = api_client.post(
            reverse("users:login"), {"username": "ali", "password": NEW_PASSWORD}, format="json"
        )
        assert signed_in.json()["plan"] == "premium"

    def test_the_kind_of_account_never_comes_from_the_client(
        self, site_owner: User, api_client: APIClient
    ) -> None:
        role = {"is_premium": True, "is_superuser": True, "is_staff": True, "plan": "owner"}

        api_client.post(
            reverse("users:signup"),
            {"first_name": "سارا", "username": "sara", "password": NEW_PASSWORD, **role},
            format="json",
        )
        client_for(site_owner).post(reverse("panel:user-list"), special_form(**role), format="json")

        sara = User.objects.get(username="sara")
        assert (sara.is_premium, sara.is_superuser, sara.is_staff) == (False, False, False)
        ali = User.objects.get(username="ali")
        assert (ali.is_premium, ali.is_superuser, ali.is_staff) == (True, False, False)

    def test_the_form_is_checked_like_signing_up(self, site_owner: User, free_user: User) -> None:
        client = client_for(site_owner)

        taken = client.post(
            reverse("panel:user-list"), special_form(free_user.username), format="json"
        )
        weak = client.post(
            reverse("panel:user-list"), special_form(password="short"), format="json"
        )

        assert taken.status_code == 400
        assert "username" in taken.json()["errors"]
        assert weak.status_code == 400
        assert "password" in weak.json()["errors"]

    def test_the_owner_upgrades_a_regular_account(self, site_owner: User, free_user: User) -> None:
        response = client_for(site_owner).post(reverse("panel:user-upgrade", args=[free_user.pk]))

        assert response.status_code == 200
        assert response.json()["plan"] == "premium"
        free_user.refresh_from_db()
        assert free_user.is_premium is True
        # The limits are gone at once.
        assert attach_image(client_for(free_user), IdeaFactory(owner=free_user)).status_code == 201

    def test_nobody_else_can_upgrade(self, premium_user: User, free_user: User) -> None:
        response = client_for(premium_user).post(reverse("panel:user-upgrade", args=[free_user.pk]))

        assert response.status_code == 403
        free_user.refresh_from_db()
        assert free_user.is_premium is False

    def test_guests_and_the_owner_are_not_upgraded_from_here(
        self, site_owner: User, guest: User
    ) -> None:
        client = client_for(site_owner)

        assert client.post(reverse("panel:user-upgrade", args=[guest.pk])).status_code == 404
        assert client.post(reverse("panel:user-upgrade", args=[site_owner.pk])).status_code == 404

    def test_the_owner_turns_a_special_account_back_into_a_regular_one(
        self, site_owner: User, premium_user: User
    ) -> None:
        idea = IdeaFactory(owner=premium_user)
        IdeaFactory(owner=premium_user)
        IdeaFactory(owner=premium_user)

        response = client_for(site_owner).post(
            reverse("panel:user-downgrade", args=[premium_user.pk])
        )

        assert response.status_code == 200
        assert response.json()["plan"] == "free"
        premium_user.refresh_from_db()
        assert premium_user.is_premium is False
        # Nothing it holds is taken away; it is only held to the limits again.
        assert Idea.objects.filter(owner=premium_user).count() == 3
        assert add_idea(client_for(premium_user)).status_code == 403
        assert attach_image(client_for(premium_user), idea).status_code == 403

    def test_the_kind_changes_back_and_forth(self, site_owner: User, free_user: User) -> None:
        client = client_for(site_owner)

        plans_seen = [
            client.post(reverse(f"panel:user-{action}", args=[free_user.pk])).json()["plan"]
            for action in ("upgrade", "downgrade", "upgrade", "downgrade")
        ]

        assert plans_seen == ["premium", "free", "premium", "free"]

    @pytest.mark.parametrize("account", ["premium_user", "free_user", "guest"])
    def test_nobody_else_can_change_a_kind(self, request, account: str) -> None:
        caller = request.getfixturevalue(account)
        target = UserFactory(is_premium=True)
        client = client_for(caller)

        assert client.post(reverse("panel:user-downgrade", args=[target.pk])).status_code == 403
        assert client.post(reverse("panel:user-upgrade", args=[target.pk])).status_code == 403
        target.refresh_from_db()
        assert target.is_premium is True

    def test_anonymous_visitors_cannot_change_a_kind(
        self, api_client: APIClient, premium_user: User
    ) -> None:
        response = api_client.post(reverse("panel:user-downgrade", args=[premium_user.pk]))

        assert response.status_code == 403
        premium_user.refresh_from_db()
        assert premium_user.is_premium is True

    def test_the_owners_own_kind_is_not_changed_from_here(self, site_owner: User) -> None:
        client = client_for(site_owner)

        assert client.post(reverse("panel:user-downgrade", args=[site_owner.pk])).status_code == 404
        site_owner.refresh_from_db()
        assert site_owner.is_superuser is True

    def test_the_count_leaves_out_the_trash(self, site_owner: User, free_user: User) -> None:
        IdeaFactory(owner=free_user)
        IdeaFactory(owner=free_user, deleted_at=timezone.now())

        listing = client_for(site_owner).get(reverse("panel:user-list")).json()["results"]

        assert listing[0]["idea_count"] == 1


class TestSite:
    def test_the_owners_telegram_is_public(self, api_client: APIClient, settings) -> None:
        settings.OWNER_TELEGRAM_USERNAME = "braindock_owner"

        assert api_client.get(reverse("site")).json()["owner_telegram"] == "braindock_owner"

    def test_without_it_there_is_nothing_to_link_to(self, api_client: APIClient, settings) -> None:
        settings.OWNER_TELEGRAM_USERNAME = ""

        assert api_client.get(reverse("site")).json()["owner_telegram"] is None

    def test_the_upload_limits_are_public(self, api_client: APIClient, settings) -> None:
        """So the interface can state them, and check a file before it travels."""
        settings.MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024

        image = api_client.get(reverse("site")).json()["uploads"]["image"]

        assert image["max_bytes"] == 10 * 1024 * 1024
        assert image["types"] == ["image/jpeg", "image/png", "image/webp"]
        assert image["formats"] == "JPEG، PNG یا WebP"
