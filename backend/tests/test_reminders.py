import threading
from datetime import UTC, datetime, timedelta

import jdatetime
import pytest
from django.db import connections
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications.models import Notification, NotificationKind
from apps.reminders import services
from apps.reminders.models import (
    DeliveryChannel,
    DeliveryStatus,
    Reminder,
    ReminderDelivery,
    ReminderRecurrence,
)
from apps.reminders.tasks import dispatch_due_reminders
from apps.users.models import User
from core.formatting import user_timezone
from tests.factories import IdeaFactory

pytestmark = pytest.mark.django_db


def tehran(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    naive = jdatetime.datetime(year, month, day, hour, minute).togregorian()
    return naive.replace(tzinfo=user_timezone()).astimezone(UTC)


def make_reminder(user: User, **overrides) -> Reminder:
    idea = overrides.pop("idea", None) or IdeaFactory(owner=user)
    fields = {
        "recurrence": ReminderRecurrence.DAILY,
        "hour": 9,
        "minute": 0,
        **overrides,
    }
    return services.set_reminder(idea=idea, **fields)


class TestSettingAReminder:
    def test_creating_one_computes_its_first_firing(self, user: User) -> None:
        reminder = make_reminder(user)

        assert reminder.next_run_at is not None
        assert reminder.next_run_at > timezone.now()

    def test_changing_the_rule_recomputes_the_firing(self, user: User) -> None:
        reminder = make_reminder(user, hour=9)
        first = reminder.next_run_at

        updated = services.set_reminder(
            idea=reminder.idea, recurrence=ReminderRecurrence.DAILY, hour=23, minute=45
        )

        assert updated.pk == reminder.pk
        assert updated.next_run_at != first

    def test_a_one_off_in_the_past_is_created_inactive(self, user: User) -> None:
        yesterday = (timezone.now() - timedelta(days=1)).astimezone(user_timezone()).date()

        reminder = make_reminder(user, recurrence=ReminderRecurrence.EXACT, exact_date=yesterday)

        assert reminder.next_run_at is None
        assert reminder.is_active is False

    def test_an_idea_holds_at_most_one_reminder(self, user: User) -> None:
        idea = IdeaFactory(owner=user)

        make_reminder(user, idea=idea, hour=9)
        make_reminder(user, idea=idea, hour=21)

        assert Reminder.objects.filter(idea=idea).count() == 1

    def test_clearing_removes_it(self, user: User) -> None:
        reminder = make_reminder(user)

        services.clear_reminder(idea=reminder.idea)

        assert Reminder.objects.count() == 0

    def test_deleting_the_idea_removes_the_reminder(self, user: User) -> None:
        reminder = make_reminder(user)

        reminder.idea.delete()

        assert Reminder.objects.count() == 0


class TestPausing:
    def test_pausing_keeps_the_configuration(self, user: User) -> None:
        reminder = make_reminder(user, hour=7, minute=30)

        services.set_active(reminder=reminder, is_active=False)
        reminder.refresh_from_db()

        assert reminder.is_active is False
        assert (reminder.hour, reminder.minute) == (7, 30)

    def test_a_paused_reminder_does_not_fire(self, user: User) -> None:
        reminder = make_reminder(user)
        services.set_active(reminder=reminder, is_active=False)
        Reminder.objects.filter(pk=reminder.pk).update(
            next_run_at=timezone.now() - timedelta(minutes=1)
        )

        dispatch_due_reminders()

        assert Notification.objects.count() == 0

    def test_resuming_moves_the_firing_forward(self, user: User) -> None:
        """A reminder switched back on should not fire for a slot that passed
        while it was silent."""
        reminder = make_reminder(user)
        services.set_active(reminder=reminder, is_active=False)
        Reminder.objects.filter(pk=reminder.pk).update(
            next_run_at=timezone.now() - timedelta(days=3)
        )
        reminder.refresh_from_db()

        services.set_active(reminder=reminder, is_active=True)
        reminder.refresh_from_db()

        assert reminder.is_active is True
        assert reminder.next_run_at > timezone.now()


class TestDispatch:
    def test_a_due_reminder_produces_a_notification(self, user: User) -> None:
        reminder = make_reminder(user)
        Reminder.objects.filter(pk=reminder.pk).update(
            next_run_at=timezone.now() - timedelta(seconds=30)
        )

        result = dispatch_due_reminders()

        assert result["fired"] == 1
        notification = Notification.objects.get()
        assert notification.owner == user
        assert notification.kind == NotificationKind.REMINDER
        assert notification.idea == reminder.idea
        assert notification.is_read is False

    def test_the_notification_reads_the_way_the_design_shows(self, user: User) -> None:
        idea = IdeaFactory(owner=user, title="سری استوری")
        reminder = make_reminder(user, idea=idea, hour=9, minute=0)
        Reminder.objects.filter(pk=reminder.pk).update(
            next_run_at=timezone.now() - timedelta(seconds=30)
        )

        dispatch_due_reminders()

        assert Notification.objects.get().text == "یادآوری: سری استوری، هر روز ساعت ۹:۰۰"

    def test_a_reminder_not_yet_due_is_left_alone(self, user: User) -> None:
        make_reminder(user)

        assert dispatch_due_reminders()["fired"] == 0
        assert Notification.objects.count() == 0

    def test_firing_advances_to_the_next_occurrence(self, user: User) -> None:
        reminder = make_reminder(user)
        Reminder.objects.filter(pk=reminder.pk).update(
            next_run_at=timezone.now() - timedelta(seconds=30)
        )

        dispatch_due_reminders()
        reminder.refresh_from_db()

        assert reminder.next_run_at > timezone.now()

    def test_a_one_off_deactivates_after_firing(self, user: User) -> None:
        yesterday = (timezone.now() - timedelta(days=1)).astimezone(user_timezone()).date()
        reminder = make_reminder(
            user, recurrence=ReminderRecurrence.EXACT, exact_date=yesterday, hour=9, minute=0
        )

        # Put the row into the state it is in at the instant it comes due: the
        # moment has arrived, and it has not fired yet.
        Reminder.objects.filter(pk=reminder.pk).update(
            next_run_at=timezone.now() - timedelta(seconds=30), is_active=True
        )

        dispatch_due_reminders()
        reminder.refresh_from_db()

        assert Notification.objects.count() == 1
        assert reminder.is_active is False
        assert reminder.next_run_at is None

    def test_an_outage_does_not_discharge_every_missed_day(self, user: User) -> None:
        """After downtime a daily reminder fires once and resumes tomorrow,
        rather than delivering one notification per missed day."""
        reminder = make_reminder(user)
        Reminder.objects.filter(pk=reminder.pk).update(
            next_run_at=timezone.now() - timedelta(days=5)
        )

        for _ in range(3):
            dispatch_due_reminders()

        assert Notification.objects.count() == 1

    def test_reminders_of_different_owners_go_to_their_own_owners(
        self, user: User, other_user: User
    ) -> None:
        mine = make_reminder(user)
        theirs = make_reminder(other_user)
        Reminder.objects.filter(pk__in=[mine.pk, theirs.pk]).update(
            next_run_at=timezone.now() - timedelta(seconds=30)
        )

        dispatch_due_reminders()

        assert Notification.objects.filter(owner=user).count() == 1
        assert Notification.objects.filter(owner=other_user).count() == 1


class TestIdempotency:
    """Delivery must happen once per slot, however many times the tick runs."""

    def test_a_delivery_row_is_written_for_the_slot(self, user: User) -> None:
        reminder = make_reminder(user)
        due_at = timezone.now() - timedelta(seconds=30)
        Reminder.objects.filter(pk=reminder.pk).update(next_run_at=due_at)

        dispatch_due_reminders()

        delivery = ReminderDelivery.objects.get()
        assert delivery.channel == DeliveryChannel.IN_APP
        assert delivery.status == DeliveryStatus.SENT
        assert delivery.sent_at is not None

    def test_replaying_the_same_slot_does_not_notify_twice(self, user: User) -> None:
        reminder = make_reminder(user)
        due_at = timezone.now() - timedelta(seconds=30)
        Reminder.objects.filter(pk=reminder.pk).update(next_run_at=due_at)
        reminder.refresh_from_db()

        # Two attempts at the same slot, as a retried task would produce.
        services.deliver_reminder(reminder=reminder, scheduled_for=due_at)
        services.deliver_reminder(reminder=reminder, scheduled_for=due_at)

        assert Notification.objects.count() == 1
        assert ReminderDelivery.objects.count() == 1

    def test_the_uniqueness_is_enforced_by_the_database(self, user: User) -> None:
        from django.db import IntegrityError, transaction

        reminder = make_reminder(user)
        slot = timezone.now()
        ReminderDelivery.objects.create(
            reminder=reminder, scheduled_for=slot, channel=DeliveryChannel.IN_APP
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            ReminderDelivery.objects.create(
                reminder=reminder, scheduled_for=slot, channel=DeliveryChannel.IN_APP
            )

    def test_a_different_slot_delivers_again(self, user: User) -> None:
        reminder = make_reminder(user)
        first = timezone.now() - timedelta(days=1)
        second = timezone.now()

        services.deliver_reminder(reminder=reminder, scheduled_for=first)
        services.deliver_reminder(reminder=reminder, scheduled_for=second)

        assert Notification.objects.count() == 2

    def test_the_same_slot_on_another_channel_is_a_separate_delivery(self, user: User) -> None:
        reminder = make_reminder(user)
        slot = timezone.now()

        ReminderDelivery.objects.create(
            reminder=reminder, scheduled_for=slot, channel=DeliveryChannel.IN_APP
        )
        ReminderDelivery.objects.create(
            reminder=reminder, scheduled_for=slot, channel=DeliveryChannel.TELEGRAM
        )

        assert ReminderDelivery.objects.count() == 2


@pytest.mark.django_db(transaction=True)
class TestConcurrentTicks:
    def test_two_ticks_at_once_deliver_once(self, django_db_setup) -> None:
        """Two workers running the same minute must not notify twice.

        Row locking makes the second worker skip the reminder; the unique
        constraint on delivery is the backstop if it ever does not.
        """
        from tests.factories import UserFactory

        user = UserFactory()
        idea = IdeaFactory(owner=user)
        reminder = services.set_reminder(
            idea=idea, recurrence=ReminderRecurrence.DAILY, hour=9, minute=0
        )
        Reminder.objects.filter(pk=reminder.pk).update(
            next_run_at=timezone.now() - timedelta(seconds=30)
        )

        errors: list[BaseException] = []

        def tick() -> None:
            try:
                dispatch_due_reminders()
            # Anything a thread raises is collected and asserted on below.
            except BaseException as error:
                errors.append(error)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=tick) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert Notification.objects.count() == 1
        assert ReminderDelivery.objects.count() == 1

        Notification.objects.all().delete()
        ReminderDelivery.objects.all().delete()
        Reminder.objects.all().delete()
        idea.delete()
        user.delete()


class TestReminderApi:
    def test_creating_through_the_api(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)

        response = auth_client.post(
            reverse("reminders:reminder-list"),
            {"idea": idea.pk, "recurrence": "daily", "hour": 9, "minute": 0},
            format="json",
        )

        assert response.status_code == 201
        assert response.json()["description"] == "هر روز ساعت ۹:۰۰"
        assert response.json()["next_run_at"] is not None

    def test_a_weekly_rule_needs_at_least_one_day(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)

        response = auth_client.post(
            reverse("reminders:reminder-list"),
            {"idea": idea.pk, "recurrence": "weekly", "hour": 9, "minute": 0},
            format="json",
        )

        assert response.status_code == 400
        assert "weekdays" in response.json()["errors"]

    def test_a_monthly_rule_needs_a_day_of_month(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)

        response = auth_client.post(
            reverse("reminders:reminder-list"),
            {"idea": idea.pk, "recurrence": "monthly", "hour": 9, "minute": 0},
            format="json",
        )

        assert response.status_code == 400
        assert "day_of_month" in response.json()["errors"]

    def test_the_exact_date_travels_as_a_jalali_triple(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)

        response = auth_client.post(
            reverse("reminders:reminder-list"),
            {
                "idea": idea.pk,
                "recurrence": "exact",
                "hour": 9,
                "minute": 0,
                "exact_date": [1408, 6, 25],
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.json()["exact_date"] == [1408, 6, 25]

    def test_an_invalid_jalali_date_is_rejected(self, auth_client: APIClient, user: User) -> None:
        idea = IdeaFactory(owner=user)

        response = auth_client.post(
            reverse("reminders:reminder-list"),
            {
                "idea": idea.pk,
                "recurrence": "exact",
                "hour": 9,
                "minute": 0,
                # Mehr has 30 days.
                "exact_date": [1405, 7, 31],
            },
            format="json",
        )

        assert response.status_code == 400

    @pytest.mark.parametrize("minute", [1, 7, 20, 59])
    def test_only_the_offered_minutes_are_accepted(
        self, auth_client: APIClient, user: User, minute: int
    ) -> None:
        """The dialog offers 0, 15, 30 and 45 only."""
        idea = IdeaFactory(owner=user)

        response = auth_client.post(
            reverse("reminders:reminder-list"),
            {"idea": idea.pk, "recurrence": "daily", "hour": 9, "minute": minute},
            format="json",
        )

        assert response.status_code == 400

    def test_switching_recurrence_clears_the_previous_parameters(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user)
        created = auth_client.post(
            reverse("reminders:reminder-list"),
            {
                "idea": idea.pk,
                "recurrence": "monthly",
                "hour": 9,
                "minute": 0,
                "day_of_month": 15,
            },
            format="json",
        ).json()

        response = auth_client.put(
            reverse("reminders:reminder-detail", args=[created["id"]]),
            {"idea": idea.pk, "recurrence": "daily", "hour": 9, "minute": 0},
            format="json",
        )

        assert response.status_code == 200
        assert response.json()["day_of_month"] is None

    def test_pause_and_resume(self, auth_client: APIClient, user: User) -> None:
        reminder = make_reminder(user)

        paused = auth_client.post(reverse("reminders:reminder-pause", args=[reminder.pk]))
        assert paused.json()["is_active"] is False

        resumed = auth_client.post(reverse("reminders:reminder-resume", args=[reminder.pk]))
        assert resumed.json()["is_active"] is True

    def test_snooze_pushes_the_firing_back(self, auth_client: APIClient, user: User) -> None:
        reminder = make_reminder(user)

        response = auth_client.post(
            reverse("reminders:reminder-snooze", args=[reminder.pk]),
            {"minutes": 60},
            format="json",
        )

        assert response.status_code == 200
        reminder.refresh_from_db()
        assert reminder.next_run_at > timezone.now() + timedelta(minutes=55)

    def test_a_reminder_cannot_be_set_on_a_foreign_idea(
        self, auth_client: APIClient, other_user: User
    ) -> None:
        foreign = IdeaFactory(owner=other_user)

        response = auth_client.post(
            reverse("reminders:reminder-list"),
            {"idea": foreign.pk, "recurrence": "daily", "hour": 9, "minute": 0},
            format="json",
        )

        assert response.status_code == 400

    def test_another_users_reminder_is_not_found(
        self, auth_client: APIClient, other_user: User
    ) -> None:
        foreign = make_reminder(other_user)

        response = auth_client.get(reverse("reminders:reminder-detail", args=[foreign.pk]))

        assert response.status_code == 404
