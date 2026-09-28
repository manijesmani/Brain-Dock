import factory
from factory.django import DjangoModelFactory

from apps.ideas.models import Category, Idea, Tag
from apps.users.models import User

DEFAULT_PASSWORD = "test-password-9271"


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@braindock.test")
    first_name = "مانی"
    # Most tests are about a feature rather than about the limits of a plan,
    # so the default account has none. Tests of the limits ask for a free
    # account or a guest by name; see tests/test_plans.py.
    is_premium = True

    @factory.post_generation
    def password(self, create: bool, extracted: str | None, **kwargs: object) -> None:
        if not create:
            return
        self.set_password(extracted or DEFAULT_PASSWORD)
        self.save(update_fields=["password"])


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    owner = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"دسته {n}")


class TagFactory(DjangoModelFactory):
    class Meta:
        model = Tag

    owner = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"تگ{n}")


class IdeaFactory(DjangoModelFactory):
    class Meta:
        model = Idea

    owner = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"ایدهٔ شمارهٔ {n}")
