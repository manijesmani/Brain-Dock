from typing import Any

from django.urls import reverse
from rest_framework import serializers

from apps.ideas.models import (
    Attachment,
    AttachmentKind,
    Category,
    Idea,
    IdeaPriority,
    IdeaStatus,
    Tag,
)


class CategorySerializer(serializers.ModelSerializer):
    idea_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "color", "idea_count", "created_at"]
        read_only_fields = ["id", "idea_count", "created_at"]

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("نام دسته نمی‌تواند خالی باشد.")

        owner = self.context["request"].user
        duplicates = Category.objects.filter(owner=owner, name__iexact=name)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError("دسته‌ای با این نام از قبل وجود دارد.")

        return name


class TagSerializer(serializers.ModelSerializer):
    idea_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tag
        fields = ["id", "name", "idea_count", "created_at"]
        read_only_fields = ["id", "idea_count", "created_at"]

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("نام تگ نمی‌تواند خالی باشد.")

        owner = self.context["request"].user
        duplicates = Tag.objects.filter(owner=owner, name__iexact=name)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError("تگی با این نام از قبل وجود دارد.")

        return name


class AttachmentSerializer(serializers.ModelSerializer):
    """Read representation of an attachment.

    The stored path is never exposed. Clients receive API URLs instead, which
    route through the ownership check before any bytes are served.
    """

    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    duration_seconds = serializers.FloatField(read_only=True)

    class Meta:
        model = Attachment
        fields = [
            "id",
            "idea",
            "kind",
            "file_url",
            "thumbnail_url",
            "original_name",
            "content_type",
            "size_bytes",
            "width",
            "height",
            "duration_ms",
            "duration_seconds",
            "created_at",
        ]
        read_only_fields = fields

    def get_file_url(self, obj: Attachment) -> str:
        return reverse("ideas:attachment-file", kwargs={"pk": obj.pk})

    def get_thumbnail_url(self, obj: Attachment) -> str | None:
        if not obj.thumbnail:
            return None
        return reverse("ideas:attachment-thumbnail", kwargs={"pk": obj.pk})


class AttachmentUploadSerializer(serializers.Serializer):
    """Write side of an upload.

    `kind` states what the client believes it is sending; the inspectors in
    apps.ideas.attachments decide whether the bytes agree.
    """

    idea = serializers.PrimaryKeyRelatedField(queryset=Idea.objects.none())
    kind = serializers.ChoiceField(choices=AttachmentKind.choices)
    file = serializers.FileField()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["idea"].queryset = Idea.objects.filter(owner=request.user)


class IdeaSerializer(serializers.ModelSerializer):
    """Read and write representation of an idea.

    Tags travel as plain names rather than ids: the editor lets the user type
    a tag that does not exist yet, and the service layer resolves names to
    records. `plain_text` is exposed but never accepted -- it is derived from
    the document on every write.
    """

    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none(),
        allow_null=True,
        required=False,
    )
    # Write-only: incoming tags are names to resolve, while the outgoing
    # representation is built in `to_representation` from the related records.
    tags = serializers.ListField(
        child=serializers.CharField(max_length=40, allow_blank=False),
        required=False,
        allow_empty=True,
        max_length=20,
        write_only=True,
    )
    is_archived = serializers.BooleanField(read_only=True)
    # Embedded so opening a note needs one request rather than two.
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Idea
        fields = [
            "id",
            "title",
            "content",
            "plain_text",
            "category",
            "tags",
            "status",
            "priority",
            "is_archived",
            "attachments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "plain_text",
            "is_archived",
            "attachments",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Restrict the category choices to the requesting user's own, so a
        # foreign primary key is rejected as invalid rather than assigned.
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["category"].queryset = Category.objects.filter(owner=request.user)

    def to_representation(self, instance: Idea) -> dict[str, Any]:
        data = super().to_representation(instance)
        data["tags"] = [tag.name for tag in instance.tags.all()]
        return data

    def validate_title(self, value: str) -> str:
        title = value.strip()
        if not title:
            raise serializers.ValidationError("عنوان نمی‌تواند خالی باشد.")
        return title

    def validate_status(self, value: str) -> str:
        # Archiving has its own endpoint so the transition stays observable
        # instead of hiding inside a generic field update.
        if value == IdeaStatus.ARCHIVED:
            raise serializers.ValidationError("برای آرشیو کردن از عملیات archive استفاده کن.")
        return value


class IdeaListSerializer(IdeaSerializer):
    """Lighter payload for list views.

    The full document and the attachment records are dropped; a row in the
    listing only needs to know whether to show the paperclip icon.
    """

    attachments = None
    has_attachments = serializers.SerializerMethodField()

    class Meta(IdeaSerializer.Meta):
        fields = [
            *(
                field
                for field in IdeaSerializer.Meta.fields
                if field not in {"content", "attachments"}
            ),
            "has_attachments",
        ]
        read_only_fields = [
            field for field in IdeaSerializer.Meta.read_only_fields if field != "attachments"
        ]

    def get_has_attachments(self, obj: Idea) -> bool:
        # Reads the prefetched rows rather than issuing a COUNT per idea.
        return bool(obj.attachments.all())


class IdeaStatusChoiceSerializer(serializers.Serializer):
    """Shape of the status and priority vocabularies exposed to the client."""

    value = serializers.CharField()
    label = serializers.CharField()


def choice_payload() -> dict[str, list[dict[str, str]]]:
    """The enums the UI needs, so Persian labels live in one place only."""
    return {
        "statuses": [{"value": v, "label": lbl} for v, lbl in IdeaStatus.choices],
        "priorities": [{"value": v, "label": lbl} for v, lbl in IdeaPriority.choices],
    }
