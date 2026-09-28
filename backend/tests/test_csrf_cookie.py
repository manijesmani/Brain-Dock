"""The CSRF cookie under the project's own name.

BrainDock runs on a subdomain beside other sites. A browser sends it every
cookie set for the parent domain as well, so a neighbour's plain `csrftoken`
arrives beside BrainDock's own. With both under one name the frontend and
Django read different ones and every write is refused; see CSRF_COOKIE_NAME
in config.settings.base.
"""

import logging

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from apps.ideas.models import Idea
from apps.users.models import User

pytestmark = pytest.mark.django_db


def signed_in(user: User) -> tuple[Client, str]:
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    client.get(reverse("users:csrf"))
    return client, client.cookies[settings.CSRF_COOKIE_NAME].value


def add_idea(client: Client, token: str | None):
    headers = {"HTTP_X_CSRFTOKEN": token} if token else {}
    return client.post(
        reverse("ideas:idea-list"),
        data='{"title": "ایدهٔ تازه"}',
        content_type="application/json",
        **headers,
    )


def test_the_cookie_is_not_the_generic_name() -> None:
    assert settings.CSRF_COOKIE_NAME == "braindock_csrftoken"


def test_a_neighbours_csrftoken_cookie_changes_nothing(user: User) -> None:
    client, token = signed_in(user)
    # What another site on the parent domain leaves behind.
    client.cookies["csrftoken"] = "n" * 32

    response = add_idea(client, token)

    assert response.status_code == 201
    assert Idea.objects.count() == 1


def test_the_neighbours_token_is_not_accepted_instead(user: User) -> None:
    client, _ = signed_in(user)
    client.cookies["csrftoken"] = "n" * 32

    response = add_idea(client, "n" * 32)

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_a_refusal_is_logged_with_its_reason(user: User, caplog) -> None:
    client, _ = signed_in(user)

    with caplog.at_level(logging.WARNING, logger="core.exceptions"):
        response = add_idea(client, None)

    assert response.status_code == 403
    assert "CSRF check failed on /api/ideas/: CSRF Failed: CSRF token missing." in caplog.text
