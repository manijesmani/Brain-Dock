from django.apps import AppConfig


class UsersConfig(AppConfig):
    # The package lives under `apps/`, but the app label stays short so
    # AUTH_USER_MODEL and every relation reads as "users.User".
    name = "apps.users"
    label = "users"
    verbose_name = "Users"
