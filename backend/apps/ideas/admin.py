from django.contrib import admin

from apps.ideas.models import Attachment, Category, Idea, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "color", "created_at")
    list_filter = ("color",)
    search_fields = ("name",)
    autocomplete_fields = ("owner",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    search_fields = ("name",)
    autocomplete_fields = ("owner",)


@admin.register(Idea)
class IdeaAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "priority", "category", "updated_at")
    list_filter = ("status", "priority")
    search_fields = ("title", "plain_text")
    autocomplete_fields = ("owner", "category")
    filter_horizontal = ("tags",)
    readonly_fields = ("plain_text", "created_at", "updated_at")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("__str__", "idea", "kind", "size_bytes", "duration_ms", "created_at")
    list_filter = ("kind",)
    autocomplete_fields = ("owner", "idea")
    readonly_fields = (
        "content_type",
        "size_bytes",
        "width",
        "height",
        "duration_ms",
        "created_at",
        "updated_at",
    )
