from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.users import plans
from apps.users.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "plan",
        "is_premium",
        "is_telegram_linked",
        "stale_after_days",
        "is_staff",
    )
    # Premium is granted here, so it can be ticked straight from the list.
    list_editable = ("is_premium",)
    list_filter = (*BaseUserAdmin.list_filter, "is_premium", "is_guest", "stale_after_days")

    fieldsets = (
        *BaseUserAdmin.fieldsets,
        (
            "BrainDock",
            {
                "fields": (
                    "is_premium",
                    "is_guest",
                    "telegram_chat_id",
                    "telegram_linked_at",
                    "stale_after_days",
                )
            },
        ),
    )

    # A guest stops being one by signing up, never by an edit here.
    readonly_fields = ("telegram_linked_at", "is_guest")

    @admin.display(description="نوع حساب")
    def plan(self, obj: User) -> str:
        return plans.PLAN_LABELS[plans.plan_of(obj)]

    @admin.display(boolean=True, description="تلگرام متصل است")
    def is_telegram_linked(self, obj: User) -> bool:
        return obj.is_telegram_linked
