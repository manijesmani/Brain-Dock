from django.apps import AppConfig


class IdeasConfig(AppConfig):
    name = "apps.ideas"
    label = "ideas"
    verbose_name = "Ideas"

    def ready(self) -> None:
        from apps.ideas import signals  # noqa: F401
