import pytest
from rest_framework.test import APIClient

from apps.users.models import User
from tests.factories import DEFAULT_PASSWORD, UserFactory


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user() -> User:
    return UserFactory()


@pytest.fixture
def other_user() -> User:
    """A second account, used to prove records never cross between owners."""
    return UserFactory()


@pytest.fixture
def auth_client(api_client: APIClient, user: User) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def password() -> str:
    return DEFAULT_PASSWORD
