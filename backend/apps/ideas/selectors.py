"""Read paths for the ideas app.

Every selector takes the requesting user and filters on ownership. Views are
expected to go through these rather than touching the managers directly, so
there is one place to audit for cross-tenant leaks.
"""

from django.db.models import QuerySet

from apps.ideas.models import Attachment, Category, Idea, IdeaStatus, Tag
from apps.users.models import User


def category_queryset(*, owner: User) -> QuerySet[Category]:
    return Category.objects.filter(owner=owner)


def tag_queryset(*, owner: User) -> QuerySet[Tag]:
    return Tag.objects.filter(owner=owner)


def idea_queryset(*, owner: User) -> QuerySet[Idea]:
    return (
        Idea.objects.filter(owner=owner)
        .select_related("category")
        .prefetch_related("tags", "attachments")
    )


def attachment_queryset(*, owner: User) -> QuerySet[Attachment]:
    return Attachment.objects.filter(owner=owner).select_related("idea")


def active_idea_queryset(*, owner: User) -> QuerySet[Idea]:
    """Ideas that are not archived -- what every screen but the archive shows."""
    return idea_queryset(owner=owner).exclude(status=IdeaStatus.ARCHIVED)


def archived_idea_queryset(*, owner: User) -> QuerySet[Idea]:
    return idea_queryset(owner=owner).filter(status=IdeaStatus.ARCHIVED)
