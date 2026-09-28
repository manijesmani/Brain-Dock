"""remove_users_except_owner: every other account goes, none of their ideas do."""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.ideas.models import Attachment, AttachmentKind, Category, Idea, IdeaStatus, Tag
from apps.ideas.services import create_attachment, resolve_tags
from apps.notifications.models import Notification, NotificationKind
from apps.reminders import services as reminder_services
from apps.reminders.models import Reminder, ReminderRecurrence
from apps.users import services as user_services
from apps.users.models import User
from tests.factories import CategoryFactory, IdeaFactory, UserFactory
from tests.media_fixtures import image_upload

pytestmark = pytest.mark.django_db


@pytest.fixture
def local(settings):
    """The command runs only with DEBUG on; the test runner turns it off."""
    settings.DEBUG = True
    return settings


@pytest.fixture
def owner() -> User:
    return UserFactory(username="mani", is_premium=False, is_superuser=True)


def run(*args: str) -> str:
    out = StringIO()
    call_command("remove_users_except_owner", "--no-input", *args, stdout=out)
    return out.getvalue()


def line(output: str, label: str) -> str:
    return next(row.strip() for row in output.splitlines() if row.strip().startswith(label))


class TestWhatItDoes:
    def test_only_the_owner_is_left(self, local, owner: User) -> None:
        UserFactory(is_premium=False)
        UserFactory(is_premium=True)
        user_services.create_guest()

        output = run()

        assert list(User.objects.values_list("username", flat=True)) == ["mani"]
        assert line(output, "users removed") == "users removed: 3"
        assert line(output, "guests") == "guests: 1"
        assert line(output, "regular accounts") == "regular accounts: 1"
        assert line(output, "special accounts") == "special accounts: 1"

    def test_every_idea_moves_to_the_owner(self, local, owner: User) -> None:
        someone = UserFactory(is_premium=False)
        guest = user_services.create_guest()
        kept = [
            IdeaFactory(owner=someone),
            IdeaFactory(owner=someone, status=IdeaStatus.ARCHIVED),
            IdeaFactory(owner=someone, deleted_at=timezone.now()),
            IdeaFactory(owner=guest),
        ]
        before = {idea.pk: Idea.objects.get(pk=idea.pk).updated_at for idea in kept}

        output = run()

        assert Idea.objects.count() == 4
        assert set(Idea.objects.values_list("owner", flat=True)) == {owner.pk}
        # Changing hands is not an edit, and the trash stays the trash.
        assert {idea.pk: idea.updated_at for idea in Idea.objects.all()} == before
        assert Idea.objects.in_trash().count() == 1
        assert line(output, "ideas moved to the owner") == "ideas moved to the owner: 4"
        assert line(output, "archived among them") == "archived among them: 1"
        assert line(output, "in the trash among them") == "in the trash among them: 1"

    def test_attachments_and_reminders_go_with_their_ideas(self, local, owner: User) -> None:
        someone = UserFactory(is_premium=True)
        idea = IdeaFactory(owner=someone)
        attachment = create_attachment(idea=idea, upload=image_upload(), kind=AttachmentKind.IMAGE)
        reminder_services.set_reminder(
            idea=idea, recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )

        output = run()

        attachment.refresh_from_db()
        assert attachment.owner == owner
        assert attachment.file.storage.exists(attachment.file.name)
        reminder = Reminder.objects.get()
        # Moved, but silent: the owner is not suddenly reminded of it.
        assert (reminder.owner, reminder.idea_id, reminder.is_active) == (owner, idea.pk, False)
        assert line(output, "attachments moved") == "attachments moved: 1"
        assert line(output, "reminders moved, paused") == "reminders moved, paused: 1"

    def test_categories_and_tags_merge_by_name(self, local, owner: User) -> None:
        someone = UserFactory(is_premium=True)
        owners_work = CategoryFactory(owner=owner, name="کار")
        theirs_work = CategoryFactory(owner=someone, name="کار")
        theirs_travel = CategoryFactory(owner=someone, name="سفر")
        first = IdeaFactory(owner=someone, category=theirs_work)
        second = IdeaFactory(owner=someone, category=theirs_travel)
        resolve_tags(owner=owner, names=["کتاب"])
        first.tags.set(resolve_tags(owner=someone, names=["کتاب", "فیلم"]))

        output = run()

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.category == owners_work
        assert second.category.owner == owner
        assert second.category.name == "سفر"
        assert Category.objects.filter(owner=owner).count() == 2
        assert sorted(first.tags.values_list("name", flat=True)) == ["فیلم", "کتاب"]
        assert set(first.tags.values_list("owner", flat=True)) == {owner.pk}
        assert Tag.objects.count() == 2
        assert line(output, "categories moved") == "categories moved: 1, merged: 1"
        assert line(output, "tags moved") == "tags moved: 1, merged: 1"

    def test_what_was_theirs_alone_goes_with_them(self, local, owner: User) -> None:
        someone = UserFactory(is_premium=True)
        idea = IdeaFactory(owner=someone)
        Notification.objects.create(
            owner=someone, kind=NotificationKind.REMINDER, text="یادآوری", idea=idea
        )

        output = run()

        assert not Notification.objects.exists()
        assert Idea.objects.filter(pk=idea.pk, owner=owner).exists()
        assert line(output, "their notifications removed") == "their notifications removed: 1"

    def test_running_it_again_changes_nothing(self, local, owner: User) -> None:
        IdeaFactory(owner=UserFactory(is_premium=False))
        run()

        output = run()

        assert "Nothing to do" in output
        assert line(output, "users removed") == "users removed: 0"
        assert line(output, "ideas moved to the owner") == "ideas moved to the owner: 0"
        assert Idea.objects.filter(owner=owner).count() == 1

    def test_a_dry_run_changes_nothing(self, local, owner: User) -> None:
        someone = UserFactory(is_premium=False)
        IdeaFactory(owner=someone)

        output = run("--dry-run")

        assert User.objects.filter(pk=someone.pk).exists()
        assert Idea.objects.get().owner == someone
        assert line(output, "users removed") == "users removed: 1"
        assert "nothing was changed" in output

    def test_the_owner_can_be_named(self, local) -> None:
        UserFactory(username="keeper", is_premium=True)
        UserFactory(username="admin", is_superuser=True)

        run("--owner", "keeper")

        assert list(User.objects.values_list("username", flat=True)) == ["keeper"]


class TestWhenItRefuses:
    def test_not_without_debug(self, settings, owner: User) -> None:
        settings.DEBUG = False
        UserFactory()

        with pytest.raises(CommandError, match="DEBUG is off"):
            run()

        assert User.objects.count() == 2

    def test_not_without_one_clear_owner(self, local) -> None:
        UserFactory(is_superuser=True)
        UserFactory(is_superuser=True)

        with pytest.raises(CommandError, match="found 2"):
            run()

        assert User.objects.count() == 2

    def test_not_for_an_owner_that_does_not_exist(self, local, owner: User) -> None:
        with pytest.raises(CommandError, match="no account named"):
            run("--owner", "nobody")

    def test_asks_before_deleting(self, local, owner: User, monkeypatch) -> None:
        UserFactory()
        monkeypatch.setattr("builtins.input", lambda prompt: "no")

        with pytest.raises(CommandError, match="Cancelled"):
            call_command("remove_users_except_owner", stdout=StringIO())

        assert User.objects.count() == 2
        assert Attachment.objects.count() == 0
