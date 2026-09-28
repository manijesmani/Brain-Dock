"""Read paths for the ideas app.

Every selector takes the requesting user and filters on ownership. Views are
expected to go through these rather than touching the managers directly, so
there is one place to audit for cross-tenant leaks.

The same goes for the trash: an idea in it is left out here, so no listing,
count, search or detail page reaches it. Only `trashed_idea_queryset` does.
"""

from datetime import timedelta

from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.db.models import Count, F, Q, QuerySet
from django.utils import timezone

from apps.ideas.models import Attachment, Category, Idea, IdeaStatus, Tag
from apps.ideas.persian import normalize_persian
from apps.users.models import User

# Counts ideas through a relation -- a category's, a tag's, an account's --
# without the ones in the trash.
OUTSIDE_TRASH_COUNT = Q(ideas__deleted_at__isnull=True)


def count_ideas() -> Count:
    return Count("ideas", filter=OUTSIDE_TRASH_COUNT, distinct=True)


def category_queryset(*, owner: User) -> QuerySet[Category]:
    return Category.objects.filter(owner=owner)


def tag_queryset(*, owner: User) -> QuerySet[Tag]:
    return Tag.objects.filter(owner=owner)


def idea_queryset(*, owner: User) -> QuerySet[Idea]:
    return (
        Idea.objects.filter(owner=owner)
        .outside_trash()
        .select_related("category")
        .prefetch_related("tags", "attachments")
    )


def trashed_idea_queryset(*, owner: User) -> QuerySet[Idea]:
    """The owner's trash, most recently deleted first."""
    return (
        Idea.objects.filter(owner=owner)
        .in_trash()
        .select_related("category")
        .prefetch_related("tags", "attachments")
        .order_by("-deleted_at", "-id")
    )


def attachment_queryset(*, owner: User) -> QuerySet[Attachment]:
    # An idea in the trash is out of reach, its files with it, until it is
    # taken back out.
    return Attachment.objects.filter(owner=owner, idea__deleted_at__isnull=True).select_related(
        "idea"
    )


# Below this trigram score a match is noise rather than a near-miss.
TRIGRAM_THRESHOLD = 0.3


def search_ideas(*, queryset: QuerySet[Idea], term: str) -> QuerySet[Idea]:
    """Narrows and ranks a queryset by a Persian search term.

    Two mechanisms run together because neither is sufficient alone:

    * Full-text search over `search_vector` handles multi-word queries and
      produces the ranking. It matches whole tokens only -- PostgreSQL has no
      Persian dictionary, so the `simple` configuration does not stem, and a
      partial word finds nothing.
    * A substring match over `search_text`, backed by a trigram index, covers
      exactly that gap: the fragment a user actually types.

    Both sides are compared in normalised form, so the Arabic and Persian
    spellings of a word, and a compound written with or without a zero-width
    non-joiner, reach the same result.
    """
    normalized = normalize_persian(term)
    if not normalized:
        return queryset

    # `websearch` accepts quoted phrases and OR without ever raising on
    # malformed input, which a search box will certainly receive.
    query = SearchQuery(normalized, config="simple", search_type="websearch")

    return (
        queryset.annotate(
            rank=SearchRank(F("search_vector"), query),
            similarity=TrigramSimilarity("search_text", normalized),
        )
        .filter(
            Q(search_vector=query)
            | Q(search_text__icontains=normalized)
            | Q(similarity__gte=TRIGRAM_THRESHOLD)
        )
        .order_by("-rank", "-similarity", "-created_at")
    )


# Statuses an idea can be neglected in. Something already finished or in
# progress is not being forgotten.
NEGLECTABLE_STATUSES = [IdeaStatus.IDEA, IdeaStatus.PLANNED]


def stale_condition(*, threshold_days: int) -> Q:
    """The single definition of a stale idea.

    Used by the dashboard's filter and by the periodic digest, so the list a
    user sees and the alert they receive can never disagree.
    """
    return Q(
        status__in=NEGLECTABLE_STATUSES,
        updated_at__lt=timezone.now() - timedelta(days=threshold_days),
    )


def stale_idea_queryset(*, owner: User) -> QuerySet[Idea]:
    """The owner's neglected ideas, by their own threshold."""
    return idea_queryset(owner=owner).filter(stale_condition(threshold_days=owner.stale_after_days))


def active_idea_queryset(*, owner: User) -> QuerySet[Idea]:
    """Ideas that are not archived -- what every screen but the archive shows."""
    return idea_queryset(owner=owner).exclude(status=IdeaStatus.ARCHIVED)


def archived_idea_queryset(*, owner: User) -> QuerySet[Idea]:
    return idea_queryset(owner=owner).filter(status=IdeaStatus.ARCHIVED)
