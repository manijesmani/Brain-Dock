"""Everything a person reads from the API is Persian.

DRF's Persian catalogue covers most messages. core.exceptions rewrites the
rest -- the ones that stay English, and the literal translations -- in the
one place every error passes through.
"""

import re

import pytest
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from apps.ideas.models import AttachmentKind
from apps.reminders import services as reminder_services
from apps.reminders.models import ReminderRecurrence
from apps.users.models import User
from tests.factories import CategoryFactory, IdeaFactory

pytestmark = pytest.mark.django_db

LATIN = re.compile(r"[A-Za-z]")


@pytest.fixture(autouse=True)
def clear_throttle_cache() -> None:
    cache.clear()


class TestWholeRequestFailures:
    def test_a_body_that_is_not_json(self, auth_client: APIClient) -> None:
        response = auth_client.post(
            reverse("ideas:idea-list"), "{broken", content_type="application/json"
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "داده‌های ارسالی قابل خواندن نیست."

    def test_a_missing_csrf_token(self, user: User) -> None:
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)

        response = client.post(
            reverse("ideas:idea-list"), '{"title": "x"}', content_type="application/json"
        )

        body = response.json()
        assert response.status_code == 403
        assert body["code"] == "csrf_failed"
        assert not LATIN.search(body["detail"])

    def test_too_many_requests(self, api_client: APIClient) -> None:
        for _ in range(12):
            response = api_client.post(
                reverse("users:login"), {"username": "x", "password": "y"}, format="json"
            )

        assert response.status_code == 429
        assert response.json()["detail"] == "تعداد درخواست‌ها زیاد بود. کمی بعد دوباره تلاش کن."

    def test_signed_out(self, api_client: APIClient) -> None:
        response = api_client.get(reverse("ideas:idea-list"))

        assert response.json()["detail"] == "برای این کار باید وارد شوی."

    def test_a_record_that_is_not_there(self, auth_client: APIClient) -> None:
        response = auth_client.get(reverse("ideas:idea-detail", args=[999999]))

        assert response.json()["detail"] == "چیزی که دنبالش بودی پیدا نشد."

    def test_a_method_that_is_not_offered(self, auth_client: APIClient) -> None:
        response = auth_client.put(reverse("notifications:notification-read-all"))

        assert response.status_code == 405
        assert response.json()["detail"] == "این روش درخواست پشتیبانی نمی‌شود."


class TestFieldMessages:
    def test_a_record_that_does_not_exist(self, auth_client: APIClient) -> None:
        """DRF's own wording names the database key and the word "Object"."""
        response = auth_client.post(
            reverse("ideas:idea-list"), {"title": "x", "category": 999999}, format="json"
        )

        assert response.json()["errors"]["category"] == ["مورد انتخاب‌شده پیدا نشد."]

    def test_a_value_too_long_names_its_limit(self, auth_client: APIClient) -> None:
        response = auth_client.post(reverse("ideas:idea-list"), {"title": "x" * 300}, format="json")

        assert response.json()["detail"] == "این مقدار نباید بیشتر از ۲۰۰ حرف باشد."

    def test_a_number_out_of_range(self, auth_client: APIClient) -> None:
        response = auth_client.patch(reverse("users:me"), {"stale_after_days": 91}, format="json")

        assert response.json()["detail"] == "این مقدار باید حداکثر ۹۰ باشد."

    def test_a_message_of_the_apps_own_is_kept(self, auth_client: APIClient, user: User) -> None:
        CategoryFactory(owner=user, name="کار")

        response = auth_client.post(
            reverse("ideas:category-list"), {"name": "کار", "color": "#3B82F6"}, format="json"
        )

        assert response.json()["detail"] == "دسته‌ای با این نام از قبل وجود دارد."


class TestUploadMessages:
    def upload(self, client: APIClient, idea_id: int, file):
        return client.post(
            reverse("ideas:attachment-list"),
            {"idea": idea_id, "kind": AttachmentKind.IMAGE, "file": file},
            format="multipart",
        )

    def test_a_file_that_is_not_a_picture_names_the_formats(
        self, auth_client: APIClient, user: User
    ) -> None:
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self.upload(
            auth_client, IdeaFactory(owner=user).pk, SimpleUploadedFile("a.heic", b"not a picture")
        )

        assert response.status_code == 400
        assert "JPEG، PNG یا WebP" in response.json()["detail"]

    def test_a_picture_too_large_says_the_limit_in_persian(
        self, auth_client: APIClient, user: User, settings
    ) -> None:
        import os
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        # Noise does not compress, so this is well over a megabyte.
        buffer = BytesIO()
        Image.frombytes("RGB", (1000, 1000), os.urandom(3_000_000)).save(
            buffer, format="JPEG", quality=95
        )
        settings.MAX_IMAGE_UPLOAD_BYTES = 1024 * 1024

        response = self.upload(
            auth_client,
            IdeaFactory(owner=user).pk,
            SimpleUploadedFile("noise.jpg", buffer.getvalue(), content_type="image/jpeg"),
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "حجم عکس نباید از ۱ مگابایت بیشتر باشد."


class TestSnooze:
    def test_a_bad_value_is_refused_rather_than_crashing(
        self, auth_client: APIClient, user: User
    ) -> None:
        reminder = reminder_services.set_reminder(
            idea=IdeaFactory(owner=user), recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )

        response = auth_client.post(
            reverse("reminders:reminder-snooze", args=[reminder.pk]),
            {"minutes": "abc"},
            format="json",
        )

        assert response.status_code == 400
        assert not LATIN.search(response.json()["detail"])

    def test_it_is_an_hour_by_default(self, auth_client: APIClient, user: User) -> None:
        reminder = reminder_services.set_reminder(
            idea=IdeaFactory(owner=user), recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )

        response = auth_client.post(reverse("reminders:reminder-snooze", args=[reminder.pk]))

        assert response.status_code == 200
