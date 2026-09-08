"""Declarative filters for the idea listing.

The vocabulary mirrors the browse toolbar in the design reference exactly:
status, priority, tag and category dropdowns, a search box, and four sort
orders. Anything the toolbar cannot express is not offered here either.
"""

from django.db.models import Case, IntegerField, QuerySet, Value, When
from django_filters import rest_framework as filters

from apps.ideas.models import Idea, IdeaPriority, IdeaStatus
from apps.ideas.selectors import search_ideas, stale_condition

# The status dropdown deliberately omits `archived`: the archive is its own
# screen, reached with `?archived=true`, not a value inside this filter.
BROWSABLE_STATUSES = [
    (IdeaStatus.IDEA, IdeaStatus.IDEA.label),
    (IdeaStatus.PLANNED, IdeaStatus.PLANNED.label),
    (IdeaStatus.DOING, IdeaStatus.DOING.label),
    (IdeaStatus.DONE, IdeaStatus.DONE.label),
]

SORT_CHOICES = [
    ("new", "تازه‌ترین"),
    ("old", "قدیمی‌ترین"),
    ("touch", "آخرین تغییر"),
    ("priority", "اولویت"),
]

# High first, matching the ranking in the design reference. Alphabetical order
# on the stored value would put "high" before "low" before "mid", which is
# meaningless.
PRIORITY_RANK = Case(
    When(priority=IdeaPriority.HIGH, then=Value(0)),
    When(priority=IdeaPriority.MID, then=Value(1)),
    When(priority=IdeaPriority.LOW, then=Value(2)),
    default=Value(3),
    output_field=IntegerField(),
)


class IdeaFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=BROWSABLE_STATUSES)
    priority = filters.ChoiceFilter(choices=IdeaPriority.choices)
    category = filters.NumberFilter(field_name="category_id")
    # Ideas untouched for longer than the owner's own threshold. The dashboard
    # reads this; the periodic job that turns it into a notification is phase 7.
    stale = filters.BooleanFilter(method="filter_stale")
    # Tags are addressed by name, which is what the dropdown shows and what
    # the editor accepts.
    tag = filters.CharFilter(method="filter_by_tag")
    search = filters.CharFilter(method="filter_by_search")
    sort = filters.ChoiceFilter(choices=SORT_CHOICES, method="apply_sort", empty_label=None)

    class Meta:
        model = Idea
        fields = ["status", "priority", "category", "tag", "search", "sort", "stale"]

    def filter_by_tag(self, queryset: QuerySet[Idea], name: str, value: str) -> QuerySet[Idea]:
        return queryset.filter(tags__name__iexact=value.strip())

    def filter_stale(self, queryset: QuerySet[Idea], name: str, value: bool) -> QuerySet[Idea]:
        """Defers to the shared definition in apps.ideas.selectors."""
        condition = stale_condition(threshold_days=self.request.user.stale_after_days)

        return queryset.filter(condition) if value else queryset.exclude(condition)

    def filter_by_search(self, queryset: QuerySet[Idea], name: str, value: str) -> QuerySet[Idea]:
        return search_ideas(queryset=queryset, term=value)

    def apply_sort(self, queryset: QuerySet[Idea], name: str, value: str) -> QuerySet[Idea]:
        if value == "old":
            return queryset.order_by("created_at")
        if value == "touch":
            return queryset.order_by("-updated_at")
        if value == "priority":
            return queryset.annotate(priority_rank=PRIORITY_RANK).order_by(
                "priority_rank", "-created_at"
            )
        return queryset.order_by("-created_at")
