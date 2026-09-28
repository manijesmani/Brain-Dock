"""The profile picture: upload, shape, replacement, removal and delivery."""

from io import BytesIO

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.users.models import User
from tests.media_fixtures import exif_with_gps, image_upload

pytestmark = pytest.mark.django_db


def upload(client: APIClient, file: SimpleUploadedFile):
    return client.post(reverse("users:avatar"), {"file": file}, format="multipart")


def stored_image(user: User) -> Image.Image:
    user.refresh_from_db()
    with user.avatar.open("rb") as handle:
        image = Image.open(BytesIO(handle.read()))
        image.load()
    return image


class TestAvatarUpload:
    def test_a_picture_is_kept_and_advertised(self, auth_client: APIClient, user: User) -> None:
        response = upload(auth_client, image_upload(size=(600, 400)))

        assert response.status_code == 200
        assert response.json()["avatar_url"].startswith(reverse("users:avatar") + "?v=")
        assert auth_client.get(reverse("users:me")).json()["avatar_url"] is not None

    def test_it_is_cut_to_a_centred_square(self, auth_client: APIClient, user: User) -> None:
        upload(auth_client, image_upload(size=(600, 400)))

        assert stored_image(user).size == (400, 400)

    def test_a_large_picture_is_scaled_down_to_the_limit(
        self, auth_client: APIClient, user: User, settings
    ) -> None:
        settings.AVATAR_SIZE = 256

        upload(auth_client, image_upload(size=(1200, 900)))

        assert stored_image(user).size == (256, 256)

    def test_location_metadata_is_removed(self, auth_client: APIClient, user: User) -> None:
        upload(auth_client, image_upload(exif=exif_with_gps()))

        assert 0x8825 not in stored_image(user).getexif()

    def test_a_file_that_is_not_an_image_is_refused(
        self, auth_client: APIClient, user: User
    ) -> None:
        fake = SimpleUploadedFile("photo.jpg", b"not an image at all", content_type="image/jpeg")

        response = upload(auth_client, fake)

        assert response.status_code == 400
        user.refresh_from_db()
        assert not user.avatar

    def test_the_size_limit_is_enforced(self, auth_client: APIClient, settings) -> None:
        settings.MAX_AVATAR_UPLOAD_BYTES = 1024

        response = upload(auth_client, image_upload())

        assert response.status_code == 400
        assert "مگابایت" in response.json()["detail"]

    def test_a_new_picture_replaces_the_old_file(self, auth_client: APIClient, user: User) -> None:
        upload(auth_client, image_upload())
        user.refresh_from_db()
        first = user.avatar.name

        upload(auth_client, image_upload(size=(300, 300)))
        user.refresh_from_db()

        assert user.avatar.name != first
        assert not default_storage.exists(first)

    def test_signing_in_is_required(self, api_client: APIClient) -> None:
        response = upload(api_client, image_upload())

        assert response.status_code in (401, 403)


class TestAvatarRemoval:
    def test_removing_deletes_the_file(self, auth_client: APIClient, user: User) -> None:
        upload(auth_client, image_upload())
        user.refresh_from_db()
        name = user.avatar.name

        response = auth_client.delete(reverse("users:avatar"))

        assert response.status_code == 200
        assert response.json()["avatar_url"] is None
        assert not default_storage.exists(name)

    def test_removing_when_there_is_none_is_harmless(self, auth_client: APIClient) -> None:
        response = auth_client.delete(reverse("users:avatar"))

        assert response.status_code == 200
        assert response.json()["avatar_url"] is None


class TestAvatarDelivery:
    def test_the_owner_gets_the_picture(self, auth_client: APIClient, settings) -> None:
        """Without Nginx in front, as in development, Django sends the bytes."""
        upload(auth_client, image_upload())

        settings.DEBUG = True
        response = auth_client.get(reverse("users:avatar"))

        assert response.status_code == 200
        assert response["Content-Type"] == "image/jpeg"
        assert b"".join(response.streaming_content)[:2] == b"\xff\xd8"

    def test_there_is_nothing_to_get_before_an_upload(self, auth_client: APIClient) -> None:
        assert auth_client.get(reverse("users:avatar")).status_code == 404

    def test_production_delegates_the_bytes_to_nginx(
        self, auth_client: APIClient, settings
    ) -> None:
        upload(auth_client, image_upload())

        settings.DEBUG = False
        response = auth_client.get(reverse("users:avatar"))

        assert response.status_code == 200
        assert response["X-Accel-Redirect"].startswith(settings.MEDIA_INTERNAL_URL + "avatars/")
        assert response.content == b""

    def test_nobody_else_can_fetch_it(self, auth_client: APIClient, api_client: APIClient) -> None:
        upload(auth_client, image_upload())

        assert api_client.get(reverse("users:avatar")).status_code in (401, 403)
