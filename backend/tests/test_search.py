import pytest
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient

from apps.ideas.models import Idea, IdeaPriority, IdeaStatus
from apps.ideas.persian import normalize_persian
from apps.users.models import User
from tests.factories import CategoryFactory, IdeaFactory, TagFactory

pytestmark = pytest.mark.django_db


def search(client: APIClient, **params: object) -> list[dict]:
    return client.get(reverse("ideas:idea-list"), params).json()["results"]


def titles(client: APIClient, **params: object) -> list[str]:
    return [row["title"] for row in search(client, **params)]


# Strings chosen to exercise every folding rule, including several at once.
NORMALISATION_CORPUS = [
    "",
    "برنامه‌ریزی هفتگی",
    "كتاب يادداشت",
    "مُحَمَّدِ عَزیز",
    "آب و آتش",
    "کتــــاب",
    "سال ۱۴۰۵ و ١٢٣",
    "ســـلام‌علیکم",
    "  فاصله   های   زیاد  ",
    "Mixed English و فارسی",
    "إسلام أحمد ىار ة ۀ",
    "تست‏‫جهت‬",
    "ReAcT و Django",
]


class TestNormalisationParity:
    """The Python normaliser and the SQL one must never drift apart.

    Python normalises the incoming query; the database trigger normalises the
    indexed text. If the two disagree by even one character, searches quietly
    stop matching, and nothing else in the suite would notice.
    """

    @pytest.mark.parametrize("value", NORMALISATION_CORPUS)
    def test_sql_and_python_agree(self, value: str) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT braindock_normalize_fa(%s)", [value])
            from_sql = cursor.fetchone()[0]

        assert from_sql == normalize_persian(value)


class TestNormalisationRules:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("برنامه‌ریزی", "برنامه ریزی"),
            ("كتاب", "کتاب"),
            ("يادداشت", "یادداشت"),
            ("۱۴۰۵", "1405"),
            ("١٢٣", "123"),
            ("مُحَمَّد", "محمد"),
            ("کتــاب", "کتاب"),
            ("آب", "اب"),
            ("  دو   فاصله ", "دو فاصله"),
            (None, ""),
        ],
    )
    def test_folding(self, raw: str | None, expected: str) -> None:
        assert normalize_persian(raw) == expected


class TestSearchIndexing:
    def test_the_trigger_populates_both_columns_on_insert(self, user: User) -> None:
        idea = IdeaFactory(owner=user, title="برنامه‌ریزی", plain_text="محتوای آزمایشی")

        idea.refresh_from_db()

        assert "برنامه ریزی" in idea.search_text
        assert idea.search_vector is not None

    def test_the_trigger_refreshes_the_columns_on_update(self, user: User) -> None:
        idea = IdeaFactory(owner=user, title="عنوان اول")

        idea.title = "عنوان دوم"
        idea.save(update_fields=["title"])
        idea.refresh_from_db()

        assert "عنوان دوم" in idea.search_text
        assert "اول" not in idea.search_text

    def test_indexed_text_is_normalised(self, user: User) -> None:
        """The stored title keeps its original characters; only the search
        column is folded."""
        idea = IdeaFactory(owner=user, title="كتاب ۱۴۰۵")

        idea.refresh_from_db()

        assert idea.title == "كتاب ۱۴۰۵"
        assert idea.search_text.startswith("کتاب 1405")


class TestSearch:
    def test_a_whole_word_is_found(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user, title="سری استوری اینستاگرام")
        IdeaFactory(owner=user, title="بازطراحی وب‌سایت")

        assert titles(auth_client, search="استوری") == ["سری استوری اینستاگرام"]

    def test_a_partial_word_is_found_through_the_trigram_index(
        self, auth_client: APIClient, user: User
    ) -> None:
        """`simple` does not stem, so a fragment only matches via substring."""
        IdeaFactory(owner=user, title="اینستاگرام")

        assert titles(auth_client, search="اینستا") == ["اینستاگرام"]

    def test_arabic_spelling_finds_persian_text(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user, title="کتاب یادداشت")

        # Typed with Arabic kaf and yeh, which look nearly identical.
        assert titles(auth_client, search="كتاب") == ["کتاب یادداشت"]

    def test_persian_spelling_finds_arabic_text(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user, title="كتاب يادداشت")

        assert titles(auth_client, search="کتاب") == ["كتاب يادداشت"]

    def test_a_compound_typed_with_a_space_finds_one_written_with_zwnj(
        self, auth_client: APIClient, user: User
    ) -> None:
        IdeaFactory(owner=user, title="برنامه‌ریزی محتوا")

        assert titles(auth_client, search="برنامه ریزی") == ["برنامه‌ریزی محتوا"]

    def test_persian_digits_match_ascii_digits(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user, title="گزارش سال ۱۴۰۵")

        assert titles(auth_client, search="1405") == ["گزارش سال ۱۴۰۵"]

    def test_the_document_body_is_searchable(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user, title="عنوان بی‌ربط", plain_text="ترفند ادیتور")

        assert titles(auth_client, search="ترفند") == ["عنوان بی‌ربط"]

    def test_a_title_match_outranks_a_body_match(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user, title="یادداشت روزانه", plain_text="ربطی ندارد")
        IdeaFactory(owner=user, title="چیز دیگر", plain_text="یادداشت در متن")

        assert titles(auth_client, search="یادداشت")[0] == "یادداشت روزانه"

    def test_a_term_that_matches_nothing_returns_nothing(
        self, auth_client: APIClient, user: User
    ) -> None:
        IdeaFactory(owner=user, title="سری استوری")

        assert titles(auth_client, search="هواپیما") == []

    def test_a_blank_term_does_not_filter(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory.create_batch(2, owner=user)

        assert len(titles(auth_client, search="   ")) == 2

    def test_search_never_crosses_owners(
        self, auth_client: APIClient, user: User, other_user: User
    ) -> None:
        IdeaFactory(owner=user, title="مال من استوری")
        IdeaFactory(owner=other_user, title="مال دیگری استوری")

        assert titles(auth_client, search="استوری") == ["مال من استوری"]

    def test_search_excludes_archived_ideas(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user, title="فعال استوری")
        IdeaFactory(owner=user, title="بایگانی استوری", status=IdeaStatus.ARCHIVED)

        assert titles(auth_client, search="استوری") == ["فعال استوری"]

    def test_search_inside_the_archive(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user, title="فعال استوری")
        IdeaFactory(owner=user, title="بایگانی استوری", status=IdeaStatus.ARCHIVED)

        assert titles(auth_client, search="استوری", archived="true") == ["بایگانی استوری"]

    def test_a_malformed_query_does_not_raise(self, auth_client: APIClient, user: User) -> None:
        """A search box will receive stray quotes and operators."""
        IdeaFactory(owner=user, title="عنوان")

        for term in ['"', "a & | b", "!!!", "() OR"]:
            assert auth_client.get(reverse("ideas:idea-list"), {"search": term}).status_code == 200


class TestFilters:
    def test_by_status(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user, title="در حال انجام", status=IdeaStatus.DOING)
        IdeaFactory(owner=user, title="ایده", status=IdeaStatus.IDEA)

        assert titles(auth_client, status="doing") == ["در حال انجام"]

    def test_by_priority(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user, title="مهم", priority=IdeaPriority.HIGH)
        IdeaFactory(owner=user, title="عادی", priority=IdeaPriority.MID)

        assert titles(auth_client, priority="high") == ["مهم"]

    def test_by_category(self, auth_client: APIClient, user: User) -> None:
        category = CategoryFactory(owner=user)
        IdeaFactory(owner=user, title="داخل دسته", category=category)
        IdeaFactory(owner=user, title="بدون دسته")

        assert titles(auth_client, category=category.pk) == ["داخل دسته"]

    def test_by_tag(self, auth_client: APIClient, user: User) -> None:
        tag = TagFactory(owner=user, name="ریلز")
        tagged = IdeaFactory(owner=user, title="با تگ")
        tagged.tags.add(tag)
        IdeaFactory(owner=user, title="بدون تگ")

        assert titles(auth_client, tag="ریلز") == ["با تگ"]

    def test_filters_combine(self, auth_client: APIClient, user: User) -> None:
        IdeaFactory(owner=user, title="هدف", status=IdeaStatus.DOING, priority=IdeaPriority.HIGH)
        IdeaFactory(
            owner=user, title="وضعیت غلط", status=IdeaStatus.IDEA, priority=IdeaPriority.HIGH
        )
        IdeaFactory(
            owner=user, title="اولویت غلط", status=IdeaStatus.DOING, priority=IdeaPriority.LOW
        )

        assert titles(auth_client, status="doing", priority="high") == ["هدف"]

    def test_archived_is_not_offered_as_a_status_filter(
        self, auth_client: APIClient, user: User
    ) -> None:
        """The archive is its own screen, so `archived` is not a dropdown value."""
        response = auth_client.get(reverse("ideas:idea-list"), {"status": "archived"})

        assert response.status_code == 400

    def test_an_unknown_filter_value_is_rejected(self, auth_client: APIClient, user: User) -> None:
        assert (
            auth_client.get(reverse("ideas:idea-list"), {"priority": "urgent"}).status_code == 400
        )

    def test_filters_do_not_apply_to_a_detail_lookup(
        self, auth_client: APIClient, user: User
    ) -> None:
        idea = IdeaFactory(owner=user, status=IdeaStatus.IDEA)

        response = auth_client.get(
            reverse("ideas:idea-detail", args=[idea.pk]), {"status": "doing"}
        )

        assert response.status_code == 200


class TestSorting:
    @pytest.fixture
    def three_ideas(self, user: User) -> None:
        from django.utils import timezone

        old = IdeaFactory(owner=user, title="قدیمی", priority=IdeaPriority.LOW)
        middle = IdeaFactory(owner=user, title="میانی", priority=IdeaPriority.HIGH)
        new = IdeaFactory(owner=user, title="تازه", priority=IdeaPriority.MID)

        now = timezone.now()
        for offset, idea in enumerate([new, middle, old]):
            Idea.objects.filter(pk=idea.pk).update(
                created_at=now - timezone.timedelta(days=offset),
                updated_at=now - timezone.timedelta(days=2 - offset),
            )

    def test_newest_first_is_the_default(self, auth_client: APIClient, three_ideas: None) -> None:
        assert titles(auth_client) == ["تازه", "میانی", "قدیمی"]

    def test_oldest_first(self, auth_client: APIClient, three_ideas: None) -> None:
        assert titles(auth_client, sort="old") == ["قدیمی", "میانی", "تازه"]

    def test_last_changed(self, auth_client: APIClient, three_ideas: None) -> None:
        assert titles(auth_client, sort="touch") == ["قدیمی", "میانی", "تازه"]

    def test_by_priority_puts_high_first(self, auth_client: APIClient, three_ideas: None) -> None:
        """Ordering on the stored value would give high, low, mid."""
        assert titles(auth_client, sort="priority") == ["میانی", "تازه", "قدیمی"]

    def test_an_unknown_sort_is_rejected(self, auth_client: APIClient) -> None:
        assert auth_client.get(reverse("ideas:idea-list"), {"sort": "sideways"}).status_code == 400
