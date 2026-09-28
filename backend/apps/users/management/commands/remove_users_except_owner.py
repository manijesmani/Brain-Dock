"""Deletes every account but the owner's, once what it wrote is the owner's.

For a development database only: it refuses to run unless DEBUG is on, and
names the database it is about to change before it changes anything.

    python manage.py remove_users_except_owner              # asks first
    python manage.py remove_users_except_owner --dry-run    # only reports
    python manage.py remove_users_except_owner --no-input

No idea is lost. Every one -- archived, in the trash or neither -- moves to
the owner with its attachments and its reminder, and its categories and tags
go with it, merged into the owner's own where the name is the same. A moved
reminder is paused, so the owner is not suddenly reminded of somebody else's
ideas; it can be switched back on from the idea. What is deleted is only what
belonged to the account alone: its notifications, its Telegram link codes and
its profile picture.

Safe to run again: with nobody left but the owner it changes nothing.
"""

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.ideas.models import Attachment, Category, Idea, IdeaStatus, Tag
from apps.reminders.models import Reminder
from apps.users.models import User


@dataclass
class Report:
    guests: int = 0
    regular_accounts: int = 0
    special_accounts: int = 0
    other_superusers: int = 0
    ideas_moved: int = 0
    of_them_archived: int = 0
    of_them_in_trash: int = 0
    attachments_moved: int = 0
    reminders_moved_and_paused: int = 0
    categories_moved: int = 0
    categories_merged: int = 0
    tags_moved: int = 0
    tags_merged: int = 0
    notifications_removed: int = 0

    @property
    def users_removed(self) -> int:
        return self.guests + self.regular_accounts + self.special_accounts + self.other_superusers


class Command(BaseCommand):
    help = "Moves every other account's ideas to the owner, then deletes it. DEBUG only."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--owner",
            help="Username of the account to keep. Defaults to the one superuser.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen, and change nothing.",
        )
        parser.add_argument(
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Do not ask for confirmation.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG:
            raise CommandError(
                "Refusing to run: DEBUG is off, so this may be a production database. "
                "This command is for a local development database only."
            )

        database = connection.settings_dict
        self.stdout.write(
            f"Database: {database['NAME']} on "
            f"{database['HOST'] or 'the local socket'}:{database['PORT'] or '5432'}"
        )

        owner = self._owner(options.get("owner"))
        others = list(User.objects.exclude(pk=owner.pk).order_by("pk"))
        self.stdout.write(f"Keeping: {owner.username} (id {owner.pk})")

        if not others:
            self.stdout.write(self.style.SUCCESS("Nothing to do: it is the only account."))
            self._print(Report())
            return

        dry_run = options["dry_run"]
        if options["interactive"] and not dry_run:
            answer = input(
                f"Delete {len(others)} account(s) after moving their ideas to "
                f"{owner.username}? Type 'yes' to continue: "
            )
            if answer.strip().lower() != "yes":
                raise CommandError("Cancelled; nothing was changed.")

        report = Report()
        avatars: list[Any] = []

        with transaction.atomic():
            for user in others:
                self._count_account(user, report)
                self._move_everything(user, owner, report)
                if user.avatar:
                    avatars.append(user.avatar)

            _, removed = User.objects.filter(pk__in=[user.pk for user in others]).delete()
            report.notifications_removed = removed.get("notifications.Notification", 0)

            # Nothing gives a deleted account's picture back, so it goes too --
            # but only once the deletion has actually been committed.
            transaction.on_commit(lambda: [avatar.delete(save=False) for avatar in avatars])

            if dry_run:
                transaction.set_rollback(True)

        self._print(report)
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: nothing was changed."))
        else:
            self.stdout.write(self.style.SUCCESS("Done."))

    def _owner(self, username: str | None) -> User:
        if username:
            owner = User.objects.filter(username=username).first()
            if owner is None:
                raise CommandError(f"There is no account named {username!r}.")
            return owner

        superusers = list(User.objects.filter(is_superuser=True))
        if len(superusers) != 1:
            raise CommandError(
                f"Expected exactly one superuser to keep, found {len(superusers)}. "
                "Name the account to keep with --owner."
            )
        return superusers[0]

    def _count_account(self, user: User, report: Report) -> None:
        if user.is_superuser:
            report.other_superusers += 1
        elif user.is_guest:
            report.guests += 1
        elif user.is_premium:
            report.special_accounts += 1
        else:
            report.regular_accounts += 1

    def _move_everything(self, user: User, owner: User, report: Report) -> None:
        # Categories and tags first: the owner may already have one by the
        # same name, and the database allows only one per name and owner.
        for category in Category.objects.filter(owner=user):
            twin = Category.objects.filter(owner=owner, name__iexact=category.name).first()
            if twin is None:
                category.owner = owner
                category.save(update_fields=["owner"])
                report.categories_moved += 1
            else:
                Idea.objects.filter(category=category).update(category=twin)
                category.delete()
                report.categories_merged += 1

        for tag in Tag.objects.filter(owner=user):
            twin = Tag.objects.filter(owner=owner, name__iexact=tag.name).first()
            if twin is None:
                tag.owner = owner
                tag.save(update_fields=["owner"])
                report.tags_moved += 1
            else:
                Idea.tags.through.objects.filter(tag=tag).update(tag=twin)
                tag.delete()
                report.tags_merged += 1

        # `update` leaves `updated_at` alone: changing hands is not an edit.
        ideas = Idea.objects.filter(owner=user)
        report.of_them_archived += ideas.filter(status=IdeaStatus.ARCHIVED).count()
        report.of_them_in_trash += ideas.in_trash().count()
        report.ideas_moved += ideas.update(owner=owner)

        report.attachments_moved += Attachment.objects.filter(owner=user).update(owner=owner)
        report.reminders_moved_and_paused += Reminder.objects.filter(owner=user).update(
            owner=owner, is_active=False
        )

    def _print(self, report: Report) -> None:
        lines = [
            f"users removed: {report.users_removed}",
            f"  guests: {report.guests}",
            f"  regular accounts: {report.regular_accounts}",
            f"  special accounts: {report.special_accounts}",
            f"  other superusers: {report.other_superusers}",
            f"ideas moved to the owner: {report.ideas_moved}",
            f"  archived among them: {report.of_them_archived}",
            f"  in the trash among them: {report.of_them_in_trash}",
            f"attachments moved: {report.attachments_moved}",
            f"reminders moved, paused: {report.reminders_moved_and_paused}",
            f"categories moved: {report.categories_moved}, merged: {report.categories_merged}",
            f"tags moved: {report.tags_moved}, merged: {report.tags_merged}",
            f"their notifications removed: {report.notifications_removed}",
        ]
        for line in lines:
            self.stdout.write(line)
