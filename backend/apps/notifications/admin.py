from django.contrib import admin

from apps.notifications.models import Notification, StaleAlert


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("__str__", "owner", "kind", "is_read", "created_at")
    list_filter = ("kind", "is_read")
    autocomplete_fields = ("owner", "idea")
    readonly_fields = ("created_at", "updated_at", "read_at")


@admin.register(StaleAlert)
class StaleAlertAdmin(admin.ModelAdmin):
    list_display = ("idea", "notified_at")
    autocomplete_fields = ("idea",)
    readonly_fields = ("created_at", "updated_at")
