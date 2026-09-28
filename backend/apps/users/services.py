"""Changes to the account that are more than a field update.

Nothing here deletes an account. A guest's ideas stay in the database for
good, like everyone else's: there is no expiry and no clean-up job.
"""

import secrets

from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction
from rest_framework import serializers

from apps.users.avatar import prepare_avatar
from apps.users.models import User

# Guest usernames start with this, and nobody may sign up with a name that
# does, so a guest can never be mistaken for a real account.
GUEST_USERNAME_PREFIX = "guest-"


def set_avatar(*, user: User, upload: UploadedFile) -> User:
    """Replaces the profile picture with a checked, squared copy of the upload."""
    content, extension = prepare_avatar(upload)
    previous = user.avatar.name if user.avatar else None

    user.avatar.save(f"avatar{extension}", content, save=False)
    user.save(update_fields=["avatar"])

    # Removed only once the new picture is in place, so a failure part way
    # leaves the old one rather than none.
    if previous:
        user.avatar.storage.delete(previous)
    return user


def remove_avatar(*, user: User) -> User:
    if user.avatar:
        name = user.avatar.name
        user.avatar = ""
        user.save(update_fields=["avatar"])
        user.avatar.storage.delete(name)
    return user


def create_guest() -> User:
    """An account for someone trying the app without signing up.

    It has no password, so the session it is signed in with is the only way
    into it.
    """
    user = User(username=f"{GUEST_USERNAME_PREFIX}{secrets.token_hex(8)}", is_guest=True)
    user.set_unusable_password()
    user.save()
    return user


def sign_up(*, first_name: str, username: str, password: str, guest: User | None = None) -> User:
    """Creates a regular account, or turns the signed-in guest into one.

    A guest keeps its row, so every idea, reminder and category written
    before signing up now belongs to the account.
    """
    user = guest if guest is not None else User()
    user.is_guest = False
    return _save_account(user, first_name=first_name, username=username, password=password)


def create_special_user(*, first_name: str, username: str, password: str) -> User:
    """A special account, made by the owner from the user panel."""
    return _save_account(
        User(is_premium=True), first_name=first_name, username=username, password=password
    )


def make_special(*, user: User) -> User:
    """Turns a regular account into a special one."""
    if not user.is_premium:
        user.is_premium = True
        user.save(update_fields=["is_premium"])
    return user


def make_regular(*, user: User) -> User:
    """Turns a special account back into a regular one.

    Nothing it holds is taken away. An account left with more ideas than a
    regular one may hold keeps them all, but adds no new one -- and no
    picture or voice -- until it is back under the limit or special again.
    """
    if user.is_premium:
        user.is_premium = False
        user.save(update_fields=["is_premium"])
    return user


def _save_account(user: User, *, first_name: str, username: str, password: str) -> User:
    user.first_name = first_name
    user.username = username
    # Stored as a salted hash, never as typed.
    user.set_password(password)

    # The serializer has already checked the name is free; this covers a
    # second request taking it in between. The savepoint keeps the failed
    # insert from poisoning the request's transaction.
    try:
        with transaction.atomic():
            user.save()
    except IntegrityError:
        raise serializers.ValidationError({"username": ["این نام کاربری گرفته شده است."]}) from None

    return user
