"""Owner-only deletion removes the account's data without affecting others."""

from datetime import timedelta

import pytest
from django.contrib.sessions.models import Session
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ideas.models import Attachment, AttachmentKind, Category, Idea, IdeaStatus, Tag
from apps.ideas.services import create_attachment
from apps.notifications.models import Notification, NotificationKind, StaleAlert
from apps.reminders.models import Reminder, ReminderDelivery
from apps.reminders.services import set_reminder
from apps.telegrambot.models import TelegramLinkToken
from apps.users import services
from apps.users.models import DeviceSession, User
from tests.factories import CategoryFactory, IdeaFactory, TagFactory, UserFactory
from tests.media_fixtures import image_upload

pytestmark = pytest.mark.django_db


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.parametrize("premium", [False, True])
def test_owner_deletes_account_and_all_its_data(premium, django_capture_on_commit_callbacks):
    owner = UserFactory(is_superuser=True)
    user = UserFactory(is_premium=premium, telegram_chat_id=1234)
    user_id = user.pk
    other = UserFactory()
    kept_idea = IdeaFactory(owner=other)
    category = CategoryFactory(owner=user)
    tag = TagFactory(owner=user)
    idea = IdeaFactory(owner=user, category=category)
    idea.tags.add(tag)
    IdeaFactory(owner=user, status=IdeaStatus.ARCHIVED)
    IdeaFactory(owner=user, deleted_at=timezone.now())
    # Seed a historical attachment as a special account; downgrading must not
    # prevent the owner's subsequent deletion of that file.
    user.is_premium = True
    attachment = create_attachment(idea=idea, upload=image_upload(), kind=AttachmentKind.IMAGE)
    user.is_premium = premium
    services.set_avatar(user=user, upload=image_upload())
    stored_files = [
        (field.storage, field.name)
        for field in (attachment.file, attachment.thumbnail, user.avatar)
    ]
    reminder = set_reminder(idea=idea, recurrence="daily", hour=9, minute=0)
    ReminderDelivery.objects.create(
        reminder=reminder, scheduled_for=timezone.now(), channel="inapp"
    )
    Notification.objects.create(
        owner=user, idea=idea, kind=NotificationKind.REMINDER, text="یادآوری"
    )
    StaleAlert.objects.create(idea=idea, notified_at=timezone.now())
    TelegramLinkToken.objects.create(user=user, expires_at=timezone.now() + timedelta(minutes=10))

    signed_in = APIClient()
    signed_in.force_login(user)
    # Visiting records the device row.
    assert signed_in.get(reverse("users:me")).status_code == 200
    session_key = signed_in.session.session_key
    unrecorded = APIClient()
    unrecorded.force_login(user)
    unrecorded_key = unrecorded.session.session_key
    other_client = APIClient()
    other_client.force_login(other)
    other_key = other_client.session.session_key

    with django_capture_on_commit_callbacks(execute=True):
        response = client_for(owner).delete(reverse("panel:user-detail", args=[user_id]))

    assert response.status_code == 204
    assert not User.objects.filter(pk=user_id).exists()
    for model in (Idea, Category, Tag, Attachment, Reminder, Notification):
        assert not model.objects.filter(owner_id=user_id).exists()
    assert not ReminderDelivery.objects.exists()
    assert not StaleAlert.objects.exists()
    assert not TelegramLinkToken.objects.filter(user_id=user_id).exists()
    assert not DeviceSession.objects.filter(user_id=user_id).exists()
    assert not Session.objects.filter(pk__in=[session_key, unrecorded_key]).exists()
    assert all(not storage.exists(name) for storage, name in stored_files)
    assert signed_in.get(reverse("users:me")).status_code == 403
    assert Idea.objects.filter(pk=kept_idea.pk).exists()
    assert Session.objects.filter(pk=other_key).exists()
    assert User.objects.filter(pk=owner.pk).exists()


@pytest.mark.parametrize(
    "attrs", [{}, {"is_premium": True}, {"is_guest": True}, {"is_staff": True}]
)
def test_non_owners_cannot_delete_users(attrs):
    target = UserFactory()
    attacker = UserFactory(is_superuser=False, **attrs)
    assert (
        client_for(attacker).delete(reverse("panel:user-detail", args=[target.pk])).status_code
        == 403
    )
    assert User.objects.filter(pk=target.pk).exists()


def test_anonymous_deletion_is_refused():
    target = UserFactory()
    assert APIClient().delete(reverse("panel:user-detail", args=[target.pk])).status_code == 403
    assert User.objects.filter(pk=target.pk).exists()


def test_owner_and_guest_cannot_be_deleted_from_panel():
    owner = UserFactory(is_superuser=True)
    another_owner = UserFactory(is_superuser=True)
    guest = services.create_guest()
    for target in (owner, another_owner, guest):
        assert (
            client_for(owner).delete(reverse("panel:user-detail", args=[target.pk])).status_code
            == 404
        )
        assert User.objects.filter(pk=target.pk).exists()


def test_deletion_respects_csrf():
    owner = UserFactory(is_superuser=True)
    target = UserFactory()
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(owner)
    assert client.delete(reverse("panel:user-detail", args=[target.pk])).status_code == 403
    assert User.objects.filter(pk=target.pk).exists()


def test_rollback_keeps_account_and_files(django_capture_on_commit_callbacks):
    user = UserFactory()
    user_id = user.pk
    attachment = create_attachment(
        idea=IdeaFactory(owner=user), upload=image_upload(), kind=AttachmentKind.IMAGE
    )
    services.set_avatar(user=user, upload=image_upload())
    stored_files = [
        (field.storage, field.name)
        for field in (attachment.file, attachment.thumbnail, user.avatar)
    ]
    with (
        django_capture_on_commit_callbacks(execute=True),
        pytest.raises(RuntimeError),
        transaction.atomic(),
    ):
        services.delete_account(user=user)
        raise RuntimeError("rollback")
    assert User.objects.filter(pk=user_id).exists()
    assert Attachment.objects.filter(pk=attachment.pk).exists()
    assert all(storage.exists(name) for storage, name in stored_files)
