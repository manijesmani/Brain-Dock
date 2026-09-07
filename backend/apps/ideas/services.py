"""Write paths for the ideas app.

Serializers validate shape; these functions own the rules. In particular
`plain_text` is derived here and nowhere else, so it can never disagree with
the stored document, and archiving goes through a named operation rather than
a raw status assignment.
"""

from collections.abc import Iterable, Sequence
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models.functions import Lower

from apps.ideas.content import extract_plain_text, sanitize_document
from apps.ideas.models import Category, Idea, IdeaPriority, IdeaStatus, Tag
from apps.users.models import User

# The status an idea returns to when it is taken out of the archive. The
# design reference resets to "idea" rather than restoring the previous value.
RESTORED_STATUS = IdeaStatus.IDEA


def create_category(*, owner: User, name: str, color: str) -> Category:
    return Category.objects.create(owner=owner, name=name.strip(), color=color)


def update_category(*, category: Category, **fields: Any) -> Category:
    if "name" in fields:
        category.name = fields["name"].strip()
    if "color" in fields:
        category.color = fields["color"]

    category.full_clean(exclude=["owner"])
    category.save()
    return category


def resolve_tags(*, owner: User, names: Iterable[str]) -> list[Tag]:
    """Maps tag names to the owner's tags, creating the ones that are new.

    Matching is case-insensitive so "React" and "react" stay one tag, which is
    what the unique constraint on the model enforces anyway.
    """
    # Keyed by the lowercased name, which is what the unique constraint on the
    # model compares, while the value keeps the casing the user typed.
    wanted: dict[str, str] = {}
    for raw in names:
        name = raw.strip()
        if name:
            wanted.setdefault(name.lower(), name)

    if not wanted:
        return []

    # The lookup has to be case-insensitive too. A plain `name__in` would miss
    # a stored "React" when the client sends "react", and the insert that
    # followed would then collide with the constraint.
    existing = {
        tag.lower_name: tag
        for tag in Tag.objects.filter(owner=owner)
        .annotate(lower_name=Lower("name"))
        .filter(lower_name__in=list(wanted))
    }

    tags: list[Tag] = []
    for key, name in wanted.items():
        tag = existing.get(key)
        if tag is None:
            tag = _create_tag(owner=owner, name=name)
        tags.append(tag)

    return tags


def _create_tag(*, owner: User, name: str) -> Tag:
    """Creates a tag, tolerating a concurrent request that got there first.

    The savepoint matters: requests run inside a transaction, so an unhandled
    IntegrityError would roll back everything, not just this insert.
    """
    try:
        with transaction.atomic():
            return Tag.objects.create(owner=owner, name=name)
    except IntegrityError:
        return Tag.objects.get(owner=owner, name__iexact=name)


@transaction.atomic
def create_idea(
    *,
    owner: User,
    title: str,
    content: Any = None,
    category: Category | None = None,
    tag_names: Sequence[str] = (),
    status: str = IdeaStatus.IDEA,
    priority: str = IdeaPriority.MID,
) -> Idea:
    document = sanitize_document(content)

    idea = Idea.objects.create(
        owner=owner,
        title=title.strip(),
        content=document,
        plain_text=extract_plain_text(document),
        category=category,
        status=status,
        priority=priority,
    )

    if tag_names:
        idea.tags.set(resolve_tags(owner=owner, names=tag_names))

    return idea


@transaction.atomic
def update_idea(*, idea: Idea, **fields: Any) -> Idea:
    """Applies a partial update. Only the keys present are touched."""
    updated: list[str] = []

    if "title" in fields:
        idea.title = fields["title"].strip()
        updated.append("title")

    if "content" in fields:
        document = sanitize_document(fields["content"])
        idea.content = document
        idea.plain_text = extract_plain_text(document)
        updated.extend(["content", "plain_text"])

    if "category" in fields:
        idea.category = fields["category"]
        updated.append("category")

    if "status" in fields:
        idea.status = fields["status"]
        updated.append("status")

    if "priority" in fields:
        idea.priority = fields["priority"]
        updated.append("priority")

    if updated:
        # `updated_at` drives the stale-idea calculation, so it has to move
        # whenever anything meaningful changes.
        idea.save(update_fields=[*updated, "updated_at"])

    if "tag_names" in fields:
        idea.tags.set(resolve_tags(owner=idea.owner, names=fields["tag_names"]))

    return idea


def archive_idea(*, idea: Idea) -> Idea:
    if idea.status == IdeaStatus.ARCHIVED:
        return idea

    idea.status = IdeaStatus.ARCHIVED
    idea.save(update_fields=["status", "updated_at"])
    return idea


def restore_idea(*, idea: Idea) -> Idea:
    if idea.status != IdeaStatus.ARCHIVED:
        return idea

    idea.status = RESTORED_STATUS
    idea.save(update_fields=["status", "updated_at"])
    return idea
