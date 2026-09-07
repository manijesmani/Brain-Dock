from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from apps.ideas.content import empty_document
from core.models import OwnedTimeStampedModel


class CategoryColor(models.TextChoices):
    """The fixed eight-colour palette from the design reference.

    Category colour is deliberately not free-form: an arbitrary colour would
    let a category dot end up indistinguishable from a status badge.
    """

    BLUE = "#3B82F6", "آبی"
    VIOLET = "#8B5CF6", "بنفش"
    CYAN = "#06B6D4", "فیروزه‌ای"
    PINK = "#F472B6", "صورتی"
    AMBER = "#F59E0B", "کهربایی"
    SLATE = "#94A3B8", "خاکستری"
    RED = "#EF4444", "قرمز"
    TEAL = "#14B8A6", "سبزآبی"


class IdeaStatus(models.TextChoices):
    IDEA = "idea", "ایده"
    PLANNED = "planned", "برنامه‌ریزی‌شده"
    DOING = "doing", "در حال انجام"
    DONE = "done", "انجام‌شده"
    ARCHIVED = "archived", "آرشیو"


class IdeaPriority(models.TextChoices):
    LOW = "low", "کم"
    MID = "mid", "متوسط"
    HIGH = "high", "زیاد"


# Statuses an idea can hold while it is still in active circulation.
ACTIVE_STATUSES = [
    IdeaStatus.IDEA,
    IdeaStatus.PLANNED,
    IdeaStatus.DOING,
    IdeaStatus.DONE,
]


class Category(OwnedTimeStampedModel):
    """A single-level grouping of ideas. No nesting, by design."""

    # Overridden purely so the reverse accessor reads `user.categories`.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
        db_index=True,
    )
    name = models.CharField(max_length=60, verbose_name="نام")
    color = models.CharField(
        max_length=7,
        choices=CategoryColor,
        default=CategoryColor.BLUE,
        verbose_name="رنگ",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "دسته"
        verbose_name_plural = "دسته‌ها"
        constraints = [
            models.UniqueConstraint(
                "owner",
                Lower("name"),
                name="unique_category_name_per_owner",
            )
        ]

    def __str__(self) -> str:
        return self.name


class Tag(OwnedTimeStampedModel):
    """A free-form label. Created on demand while editing an idea."""

    name = models.CharField(max_length=40, verbose_name="نام")

    class Meta:
        ordering = ["name"]
        verbose_name = "تگ"
        verbose_name_plural = "تگ‌ها"
        constraints = [
            models.UniqueConstraint(
                "owner",
                Lower("name"),
                name="unique_tag_name_per_owner",
            )
        ]

    def __str__(self) -> str:
        return self.name


class Idea(OwnedTimeStampedModel):
    """The central record of the product.

    Archiving is expressed through `status` alone rather than a separate
    boolean. The design reference always writes the two together -- archiving
    sets the status to `archived`, restoring sets it back to `idea` -- so a
    second field would carry no information and could only ever drift out of
    sync with the first.
    """

    title = models.CharField(max_length=200, verbose_name="عنوان")

    # A sanitised Tiptap document. See apps.ideas.content for the allow-list.
    content = models.JSONField(default=empty_document, verbose_name="محتوا")

    # Flattened rendering of `content`, kept for search and Telegram messages.
    # Always derived server-side; never accepted from the client.
    plain_text = models.TextField(blank=True, verbose_name="متن ساده")

    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ideas",
        verbose_name="دسته",
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="ideas",
        verbose_name="تگ‌ها",
    )

    status = models.CharField(
        max_length=10,
        choices=IdeaStatus,
        default=IdeaStatus.IDEA,
        verbose_name="وضعیت",
    )
    priority = models.CharField(
        max_length=4,
        choices=IdeaPriority,
        default=IdeaPriority.MID,
        verbose_name="اولویت",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "ایده"
        verbose_name_plural = "ایده‌ها"
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["owner", "-updated_at"]),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def is_archived(self) -> bool:
        return self.status == IdeaStatus.ARCHIVED
