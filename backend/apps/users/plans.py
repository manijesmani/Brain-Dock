"""What each kind of account may do.

BrainDock is open to anyone, and what someone may do depends only on the kind
of account they are using -- decided here, on the server, from the account
itself and never from anything the client sends:

* A guest has not signed up. The app opens straight into a guest account, so
  every feature can be tried without a login.
* A regular account is what signing up makes. It keeps the guest's ideas
  under a name, a username and a password, with the same limits.
* A special account has no public sign-up: only the owner makes one, from the
  user panel, or turns a regular account into one.
* The owner is the superuser created at deployment with `createsuperuser`.

Guests and regular accounts may hold FREE_IDEA_LIMIT ideas and cannot attach
images or audio; reminders and everything else are open to them. A special
account lifts both limits. Two things are the owner's alone: the Telegram bot
and the user panel.

These rules are enforced where the writes happen -- apps.ideas.services, the
Telegram views and handlers, the user panel -- and sent to the client with the
account, so the interface can show a limit before anyone runs into it.
"""

from django.conf import settings
from rest_framework.exceptions import PermissionDenied

from apps.users.models import User
from core.formatting import to_persian_digits

# Kept as the API's values; the Persian names are what people see.
GUEST = "guest"
FREE = "free"
PREMIUM = "premium"
OWNER = "owner"

PLAN_LABELS = {
    GUEST: "مهمان",
    FREE: "عادی",
    PREMIUM: "ویژه",
    OWNER: "مالک",
}


def plan_of(user: User) -> str:
    if user.is_site_owner:
        return OWNER
    if user.is_premium:
        return PREMIUM
    if user.is_guest:
        return GUEST
    return FREE


def has_premium(user: User) -> bool:
    return user.is_site_owner or user.is_premium


def idea_limit(user: User) -> int | None:
    """How many ideas the account may hold, or None for no limit."""
    return None if has_premium(user) else settings.FREE_IDEA_LIMIT


def can_attach_media(user: User) -> bool:
    return has_premium(user)


def can_use_telegram(user: User) -> bool:
    return user.is_site_owner


def can_manage_users(user: User) -> bool:
    return user.is_site_owner


class PremiumRequired(PermissionDenied):
    default_detail = "افزودن عکس و صدا مخصوص کاربر ویژه است."
    default_code = "premium_required"


class IdeaLimitReached(PermissionDenied):
    default_code = "idea_limit_reached"

    def __init__(self, limit: int) -> None:
        super().__init__(
            f"با این حساب تا {to_persian_digits(limit)} ایده می‌توانی داشته باشی. "
            "برای ایدهٔ تازه یکی را حذف کن، یا به کاربر ویژه ارتقا بگیر."
        )
