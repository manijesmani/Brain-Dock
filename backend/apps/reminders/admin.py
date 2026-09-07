from django.contrib import admin

from apps.reminders.models import Reminder, ReminderDelivery


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ("idea", "recurrence", "hour", "minute", "is_active", "next_run_at")
    list_filter = ("recurrence", "is_active")
    autocomplete_fields = ("owner", "idea")
    readonly_fields = ("next_run_at", "created_at", "updated_at")
    search_fields = ("idea__title",)


@admin.register(ReminderDelivery)
class ReminderDeliveryAdmin(admin.ModelAdmin):
    list_display = ("reminder", "scheduled_for", "channel", "status", "sent_at")
    list_filter = ("channel", "status")
    readonly_fields = ("created_at", "updated_at")
