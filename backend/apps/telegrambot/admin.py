from django.contrib import admin

from apps.telegrambot.models import TelegramLinkToken


@admin.register(TelegramLinkToken)
class TelegramLinkTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "used_at", "created_at")
    list_filter = ("used_at",)
    autocomplete_fields = ("user",)
    readonly_fields = ("token", "created_at", "updated_at")
