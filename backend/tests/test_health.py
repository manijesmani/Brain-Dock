import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
def test_health_reports_ok(api_client: APIClient) -> None:
    response = api_client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "version": "0.1.0",
    }


@pytest.mark.django_db
def test_health_does_not_require_authentication(api_client: APIClient) -> None:
    """The deployment probe runs before any session exists."""
    response = api_client.get(reverse("health"))

    assert response.status_code == 200
