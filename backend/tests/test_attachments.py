import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from apps.ideas.models import Attachment, AttachmentKind
from apps.users.models import User
from tests.factories import IdeaFactory
from tests.media_fixtures import (
    audio_upload,
    exif_with_gps,
    has_ffmpeg,
    image_bytes,
    image_upload,
    video_bytes,
)

pytestmark = pytest.mark.django_db

needs_ffmpeg = pytest.mark.skipif(not has_ffmpeg(), reason="ffmpeg is not installed")


def upload(client: APIClient, idea_id: int, file: SimpleUploadedFile, kind: str):
    return client.post(
        reverse("ideas:attachment-list"),
        {"idea": idea_id, "kind": kind, "file": file},
        format="multipart",
    )


class TestImageUpload:
    def test_an_image_is_accepted_and_described(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)

        response = upload(auth_client, idea.pk, image_upload(), AttachmentKind.IMAGE)

        assert response.status_code == 201
        body = response.json()
        assert body["kind"] == "image"
        assert body["width"] == 1200
        assert body["height"] == 900
        assert body["duration_ms"] is None
        assert body["thumbnail_url"] is not None

    def test_a_thumbnail_is_generated_within_the_bounding_box(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)

        upload(auth_client, idea.pk, image_upload(), AttachmentKind.IMAGE)

        attachment = Attachment.objects.get()
        with Image.open(attachment.thumbnail) as thumbnail:
            assert thumbnail.width <= 800
            assert thumbnail.height <= 600
            # The aspect ratio of the source must survive.
            assert round(thumbnail.width / thumbnail.height, 2) == round(1200 / 900, 2)

    def test_exif_including_gps_is_removed(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        photo = image_upload(exif=exif_with_gps())

        # The fixture really does carry GPS data before the upload.
        with Image.open(photo) as source:
            assert source.getexif().get_ifd(0x8825)
        photo.seek(0)

        upload(auth_client, idea.pk, photo, AttachmentKind.IMAGE)

        attachment = Attachment.objects.get()
        with Image.open(attachment.file) as stored:
            assert not stored.getexif().get_ifd(0x8825)

    @pytest.mark.parametrize(
        ("image_format", "name", "expected_type"),
        [
            ("PNG", "shot.png", "image/png"),
            ("WEBP", "shot.webp", "image/webp"),
        ],
    )
    def test_png_and_webp_are_accepted(
        self,
        auth_client: APIClient,
        user: User,
        image_format: str,
        name: str,
        expected_type: str,
    ) -> None:
        idea = IdeaFactory(owner=user)
        file = image_upload(name, image_format=image_format, size=(200, 200))

        response = upload(auth_client, idea.pk, file, AttachmentKind.IMAGE)

        assert response.status_code == 201
        assert response.json()["content_type"] == expected_type

    def test_a_text_file_renamed_to_jpg_is_rejected(
        self, auth_client: APIClient, user: User
    ) -> None:
        """Neither the extension nor the declared content type is trusted."""
        idea = IdeaFactory(owner=user)
        disguised = SimpleUploadedFile(
            "totally-an-image.jpg", b"#!/bin/sh\nrm -rf /\n", content_type="image/jpeg"
        )

        response = upload(auth_client, idea.pk, disguised, AttachmentKind.IMAGE)

        assert response.status_code == 400
        assert Attachment.objects.count() == 0

    def test_an_oversized_image_is_rejected(
        self, auth_client: APIClient, user: User, settings
    ) -> None:
        settings.MAX_IMAGE_UPLOAD_BYTES = 1024
        idea = IdeaFactory(owner=user)

        response = upload(auth_client, idea.pk, image_upload(), AttachmentKind.IMAGE)

        assert response.status_code == 400
        assert Attachment.objects.count() == 0

    def test_a_truncated_image_is_rejected(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        truncated = SimpleUploadedFile("broken.jpg", image_bytes()[:200], content_type="image/jpeg")

        response = upload(auth_client, idea.pk, truncated, AttachmentKind.IMAGE)

        assert response.status_code == 400


@needs_ffmpeg
class TestAudioUpload:
    def test_audio_is_accepted_and_its_duration_measured(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)

        response = upload(auth_client, idea.pk, audio_upload(seconds=1.5), AttachmentKind.AUDIO)

        assert response.status_code == 201
        body = response.json()
        assert body["kind"] == "audio"
        assert 1300 <= body["duration_ms"] <= 1700
        assert body["thumbnail_url"] is None

    def test_an_ogg_voice_message_is_accepted(self, auth_client: APIClient, user: User) -> None:
        """Telegram delivers voice notes as OGG/Opus."""
        idea = IdeaFactory(owner=user)
        voice = audio_upload("voice.ogg", codec="libopus", suffix=".ogg", content_type="audio/ogg")

        response = upload(auth_client, idea.pk, voice, AttachmentKind.AUDIO)

        assert response.status_code == 201
        assert response.json()["content_type"] == "audio/ogg"

    def test_a_video_file_is_rejected(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        clip = SimpleUploadedFile("clip.mp4", video_bytes(), content_type="audio/mpeg")

        response = upload(auth_client, idea.pk, clip, AttachmentKind.AUDIO)

        assert response.status_code == 400
        assert Attachment.objects.count() == 0

    def test_an_image_sent_as_audio_is_rejected(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)

        response = upload(auth_client, idea.pk, image_upload(), AttachmentKind.AUDIO)

        assert response.status_code == 400


class TestAttachmentDelivery:
    def test_the_stored_path_is_never_exposed(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        upload(auth_client, idea.pk, image_upload(), AttachmentKind.IMAGE)

        body = auth_client.get(reverse("ideas:attachment-list")).json()["results"][0]

        assert "/media/" not in body["file_url"]
        assert body["file_url"].endswith("/file/")

    def test_the_owner_can_download_the_file(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        created = upload(auth_client, idea.pk, image_upload(), AttachmentKind.IMAGE)

        response = auth_client.get(created.json()["file_url"])

        assert response.status_code == 200

    def test_another_user_cannot_download_the_file(
        self, api_client: APIClient, auth_client: APIClient, user: User, other_user: User
    ) -> None:
        idea = IdeaFactory(owner=user)
        created = upload(auth_client, idea.pk, image_upload(), AttachmentKind.IMAGE)

        api_client.force_authenticate(user=other_user)
        response = api_client.get(created.json()["file_url"])

        assert response.status_code == 404

    def test_an_anonymous_visitor_cannot_download_the_file(
        self, api_client: APIClient, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)
        created = upload(auth_client, idea.pk, image_upload(), AttachmentKind.IMAGE)

        assert api_client.get(created.json()["file_url"]).status_code == 403

    def test_media_root_is_not_reachable_over_http(
        self, api_client: APIClient, auth_client: APIClient, user: User, settings
    ) -> None:
        """MEDIA_URL must stay unrouted even with DEBUG on, so development
        cannot accidentally be more permissive than production."""
        idea = IdeaFactory(owner=user)
        upload(auth_client, idea.pk, image_upload(), AttachmentKind.IMAGE)
        stored = Attachment.objects.get().file.name

        response = api_client.get(f"{settings.MEDIA_URL}{stored}")

        assert response.status_code == 404

    def test_production_delegates_the_bytes_to_nginx(
        self, auth_client: APIClient, user: User, settings
    ) -> None:
        idea = IdeaFactory(owner=user)
        created = upload(auth_client, idea.pk, image_upload(), AttachmentKind.IMAGE)

        settings.DEBUG = False
        response = auth_client.get(created.json()["file_url"])

        assert response.status_code == 200
        assert response["X-Accel-Redirect"].startswith(settings.MEDIA_INTERNAL_URL)
        assert response.content == b""


class TestAttachmentLifecycle:
    def test_attachments_are_scoped_to_their_idea(self, auth_client: APIClient, user: User) -> None:
        first = IdeaFactory(owner=user)
        second = IdeaFactory(owner=user)
        upload(auth_client, first.pk, image_upload(), AttachmentKind.IMAGE)
        upload(auth_client, second.pk, image_upload(), AttachmentKind.IMAGE)

        response = auth_client.get(reverse("ideas:attachment-list"), {"idea": first.pk})

        assert response.json()["pagination"]["count"] == 1

    def test_an_attachment_cannot_be_added_to_a_foreign_idea(
        self, auth_client: APIClient, other_user: User
    ) -> None:
        foreign = IdeaFactory(owner=other_user)

        response = upload(auth_client, foreign.pk, image_upload(), AttachmentKind.IMAGE)

        assert response.status_code == 400
        assert Attachment.objects.count() == 0

    def test_deleting_an_attachment_removes_its_files(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)
        created = upload(auth_client, idea.pk, image_upload(), AttachmentKind.IMAGE)
        attachment = Attachment.objects.get()
        file_path = attachment.file.path
        thumbnail_path = attachment.thumbnail.path

        auth_client.delete(reverse("ideas:attachment-detail", args=[created.json()["id"]]))

        from pathlib import Path

        assert not Path(file_path).exists()
        assert not Path(thumbnail_path).exists()

    def test_deleting_an_idea_removes_its_attachment_files(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)
        upload(auth_client, idea.pk, image_upload(), AttachmentKind.IMAGE)
        file_path = Attachment.objects.get().file.path

        auth_client.delete(reverse("ideas:idea-detail", args=[idea.pk]))

        from pathlib import Path

        assert Attachment.objects.count() == 0
        assert not Path(file_path).exists()

    def test_an_idea_reports_its_attachments(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)
        upload(auth_client, idea.pk, image_upload(), AttachmentKind.IMAGE)

        detail = auth_client.get(reverse("ideas:idea-detail", args=[idea.pk])).json()
        listing = auth_client.get(reverse("ideas:idea-list")).json()["results"][0]

        assert len(detail["attachments"]) == 1
        assert listing["has_attachments"] is True
        assert "attachments" not in listing
