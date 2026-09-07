from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.users.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "is_telegram_linked",
        "stale_after_days",
        "is_staff",
    )
    list_filter = (*BaseUserAdmin.list_filter, "stale_after_days")

    fieldsets = (
        *BaseUserAdmin.fieldsets,
        (
            "BrainDock",
            {
                "fields": (
                    "telegram_chat_id",
                    "telegram_linked_at",
                    "stale_after_days",
                )
            },
        ),
    )

    readonly_fields = ("telegram_linked_at",)

    @admin.display(boolean=True, description="تلگرام متصل است")
    def is_telegram_linked(self, obj: User) -> bool:
        return obj.is_telegram_linked
