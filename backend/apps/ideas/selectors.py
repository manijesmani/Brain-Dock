"""Read paths for the ideas app.

Every selector takes the requesting user and filters on ownership. Views are
expected to go through these rather than touching the managers directly, so
there is one place to audit for cross-tenant leaks.
"""

from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.db.models import F, Q, QuerySet

from apps.ideas.models import Attachment, Category, Idea, IdeaStatus, Tag
from apps.ideas.persian import normalize_persian
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


def active_idea_queryset(*, owner: User) -> QuerySet[Idea]:
    """Ideas that are not archived -- what every screen but the archive shows."""
    return idea_queryset(owner=owner).exclude(status=IdeaStatus.ARCHIVED)


def archived_idea_queryset(*, owner: User) -> QuerySet[Idea]:
    return idea_queryset(owner=owner).filter(status=IdeaStatus.ARCHIVED)
