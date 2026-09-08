from typing import Any

import jdatetime
from rest_framework import serializers

from apps.ideas.models import Idea
from apps.reminders.messages import describe_schedule
from apps.reminders.models import Reminder, ReminderRecurrence

# The dialog offers only these minutes.
ALLOWED_MINUTES = (0, 15, 30, 45)


class JalaliDateField(serializers.Field):
    """A date exchanged with the client as Jalali, stored as Gregorian.

    The wire form is `[year, month, day]`, which is exactly the shape the
    design's calendar produces.
    """

    def to_representation(self, value: Any) -> list[int] | None:
        if value is None:
            return None
        jalali = jdatetime.date.fromgregorian(date=value)
        return [jalali.year, jalali.month, jalali.day]

    def to_internal_value(self, data: Any):
        if not isinstance(data, (list, tuple)) or len(data) != 3:
            raise serializers.ValidationError("تاریخ باید به شکل [سال، ماه، روز] باشد.")

        try:
            year, month, day = (int(part) for part in data)
            return jdatetime.date(year, month, day).togregorian()
        except (TypeError, ValueError):
            raise serializers.ValidationError("تاریخ شمسی معتبر نیست.") from None


class ReminderSerializer(serializers.ModelSerializer):
    idea = serializers.PrimaryKeyRelatedField(queryset=Idea.objects.none())
    exact_date = JalaliDateField(required=False, allow_null=True)

    # Read-only conveniences so the client renders the same wording the
    # notification will use, without reimplementing it.
    description = serializers.SerializerMethodField()
    next_run_at = serializers.DateTimeField(read_only=True)

    # The dashboard lists reminders and needs to show which idea each belongs
    # to; inlining the few fields it renders saves a request per row.
    idea_title = serializers.CharField(source="idea.title", read_only=True)
    idea_category_name = serializers.CharField(
        source="idea.category.name", read_only=True, default=None
    )
    idea_category_color = serializers.CharField(
        source="idea.category.color", read_only=True, default=None
    )

    class Meta:
        model = Reminder
        fields = [
            "id",
            "idea",
            "idea_title",
            "idea_category_name",
            "idea_category_color",
            "recurrence",
            "hour",
            "minute",
            "weekdays",
            "day_of_month",
            "exact_date",
            "is_active",
            "next_run_at",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "idea_title",
            "idea_category_name",
            "idea_category_color",
            "next_run_at",
            "description",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["idea"].queryset = Idea.objects.filter(owner=request.user)

    def get_description(self, obj: Reminder) -> str:
        return describe_schedule(obj)

    def validate_minute(self, value: int) -> int:
        if value not in ALLOWED_MINUTES:
            allowed = "، ".join(str(m) for m in ALLOWED_MINUTES)
            raise serializers.ValidationError(f"دقیقه باید یکی از این‌ها باشد: {allowed}")
        return value

    def validate_weekdays(self, value: list[int]) -> list[int]:
        unique = sorted(set(value))
        if any(day < 0 or day > 6 for day in unique):
            raise serializers.ValidationError("روز هفته باید بین ۰ (شنبه) و ۶ (جمعه) باشد.")
        return unique

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Each recurrence needs its own parameter and rejects the others.

        The database enforces the same rule; catching it here turns a 500 into
        a message the user can act on.
        """
        recurrence = attrs.get("recurrence") or getattr(self.instance, "recurrence", None)

        weekdays = attrs.get("weekdays", getattr(self.instance, "weekdays", []) or [])
        day_of_month = attrs.get("day_of_month", getattr(self.instance, "day_of_month", None))
        exact_date = attrs.get("exact_date", getattr(self.instance, "exact_date", None))

        errors: dict[str, str] = {}

        if recurrence == ReminderRecurrence.WEEKLY and not weekdays:
            errors["weekdays"] = "برای یادآوری هفتگی حداقل یک روز هفته انتخاب کن."
        if recurrence == ReminderRecurrence.MONTHLY and day_of_month is None:
            errors["day_of_month"] = "برای یادآوری ماهانه روز ماه را مشخص کن."
        if recurrence == ReminderRecurrence.EXACT and exact_date is None:
            errors["exact_date"] = "برای یادآوری یک‌باره تاریخ را مشخص کن."

        # Clear the parameters the chosen recurrence does not use, so the row
        # never carries a leftover from a previous rule.
        if recurrence != ReminderRecurrence.WEEKLY:
            attrs["weekdays"] = []
        if recurrence != ReminderRecurrence.MONTHLY:
            attrs["day_of_month"] = None
        if recurrence != ReminderRecurrence.EXACT:
            attrs["exact_date"] = None

        if errors:
            raise serializers.ValidationError(errors)

        return attrs
