import pytest
from rest_framework.test import APIClient

from apps.users.models import User
from tests.factories import DEFAULT_PASSWORD, UserFactory


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    """Keeps uploaded test files out of the project's real media directory."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


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
def auth_client(user: User) -> APIClient:
    """A signed-in client.

    Deliberately a separate instance from `api_client`: a test that wants both
    an authenticated and an anonymous client must get two, otherwise
    authenticating one would silently authenticate the other.
    """
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def password() -> str:
    return DEFAULT_PASSWORD
