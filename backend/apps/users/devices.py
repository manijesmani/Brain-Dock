"""The devices signed in to an account: recording them, and signing them out.

Every signed-in request passes through DeviceSessionMiddleware, which calls
`note()`: the first time a session is seen it is written down with its
browser and address, and after that its last use is brought up to date every
few minutes. Guests are left out -- a guest has the one browser, and nothing
to sign out of.

A device is a Django session, so signing one out is deleting that session:
the next request from it arrives signed out.
"""

import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.contrib.sessions.models import Session
from django.db import IntegrityError, transaction
from django.http import HttpRequest
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework.settings import api_settings

from apps.users.models import DeviceSession, User

# How often a device's last use is written down. Every request would be a
# write per request; this is precise enough for «آخرین استفاده».
REFRESH_EVERY = timedelta(minutes=5)

# Kept in the session itself, so deciding whether to write costs nothing.
SEEN_KEY = "_device_seen"


# --------------------------------------------------------------------------
# What a device is called
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceDescription:
    name: str
    # "mobile", "tablet", "desktop" or "unknown": which icon the list shows.
    kind: str


# Most specific first: Edge, Opera and Samsung's browser all say Chrome too,
# and Chrome says Safari.
BROWSERS = [
    (re.compile(r"Edg(e|A|iOS)?/"), "Edge"),
    (re.compile(r"OPR/|Opera"), "Opera"),
    (re.compile(r"SamsungBrowser/"), "Samsung Internet"),
    (re.compile(r"YaBrowser/"), "Yandex"),
    (re.compile(r"Firefox/|FxiOS/"), "Firefox"),
    (re.compile(r"Chrome/|CriOS/"), "Chrome"),
    (re.compile(r"Version/[\d.]+.*Safari/"), "Safari"),
]


def _system(user_agent: str) -> tuple[str | None, str]:
    if "iPad" in user_agent:
        return "iPad", "tablet"
    if "iPhone" in user_agent or "iPod" in user_agent:
        return "iPhone", "mobile"
    if "Android" in user_agent:
        # An Android tablet's browser leaves "Mobile" out.
        return "Android", "mobile" if "Mobile" in user_agent else "tablet"
    if "Windows" in user_agent:
        return "Windows", "desktop"
    if "CrOS" in user_agent:
        return "ChromeOS", "desktop"
    if "Macintosh" in user_agent or "Mac OS X" in user_agent:
        return "macOS", "desktop"
    if "Linux" in user_agent:
        return "Linux", "desktop"
    return None, "unknown"


def describe_user_agent(user_agent: str) -> DeviceDescription:
    """«Chrome روی Android», «Safari روی iPhone», and so on."""
    if not user_agent:
        return DeviceDescription("دستگاه نامشخص", "unknown")

    system, kind = _system(user_agent)
    browser = next((name for pattern, name in BROWSERS if pattern.search(user_agent)), None)

    if browser and system:
        return DeviceDescription(f"{browser} روی {system}", kind)
    if system:
        return DeviceDescription(f"مرورگر روی {system}", kind)
    if browser:
        return DeviceDescription(browser, kind)
    return DeviceDescription("دستگاه ناشناخته", kind)


# --------------------------------------------------------------------------
# Where a request comes from
# --------------------------------------------------------------------------


def client_ip(request: HttpRequest) -> str | None:
    """The caller's address, read the way the rate limits read it.

    Behind the proxy every request arrives from the proxy, and the caller's
    address is the entry the proxy put in X-Forwarded-For; NUM_PROXIES says
    how many proxies there are (see config.settings.prod). With none
    declared the header is only the caller's own claim, so it is ignored.
    """
    remote = request.META.get("REMOTE_ADDR")
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    proxies = api_settings.NUM_PROXIES

    address = remote
    if proxies and forwarded:
        entries = [entry.strip() for entry in forwarded.split(",")]
        address = entries[-min(proxies, len(entries))]

    try:
        return str(ipaddress.ip_address(address or ""))
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Recording
# --------------------------------------------------------------------------


def note(request: HttpRequest) -> None:
    """Writes down the device a signed-in request came from.

    Runs after the view, so a request that has just signed in is recorded
    under the session it now has. The session remembers which key was last
    written down and when, so an unchanged session costs no query at all
    between refreshes, and one whose key was just renewed is written at once.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or user.is_guest:
        return

    if not request.session.session_key:
        # Signed in just now over a session that was someone else's, or a
        # guest's: Django emptied it, and the new one has a key only once it
        # is saved -- which would otherwise happen after this.
        request.session.save()
    key = request.session.session_key
    if not key:
        return

    now = timezone.now()
    seen = request.session.get(SEEN_KEY)
    if seen and seen.get("key") == key:
        last = datetime.fromisoformat(seen["at"])
        if now - last < REFRESH_EVERY:
            return

    current = {
        "user": user,
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:512],
        "ip_address": client_ip(request),
        "last_seen_at": now,
    }
    try:
        # A savepoint: another device may have signed this one out while the
        # request was running, and its session row is then gone.
        with transaction.atomic():
            DeviceSession.objects.update_or_create(
                session_id=key,
                defaults=current,
                create_defaults={**current, "signed_in_at": now},
            )
    except IntegrityError:
        return

    request.session[SEEN_KEY] = {"key": key, "at": now.isoformat()}


# --------------------------------------------------------------------------
# Listing and signing out
# --------------------------------------------------------------------------


def _still_signed_in(session: Session, user: User) -> bool:
    """Whether a session would still let its browser in.

    A password change leaves the other sessions in the table but no longer
    valid -- Django compares the hash of the password they were made with --
    so they are checked the same way here rather than listed as signed in.
    """
    data = session.get_decoded()
    return data.get("_auth_user_id") == str(user.pk) and constant_time_compare(
        data.get("_auth_user_hash", ""), user.get_session_auth_hash()
    )


def active_devices(user: User) -> list[DeviceSession]:
    """The account's signed-in devices. Ones no longer valid are cleared away."""
    devices = list(
        DeviceSession.objects.filter(user=user, session__expire_date__gt=timezone.now())
        .select_related("session")
        .order_by("-last_seen_at", "-pk")
    )

    signed_out = [device for device in devices if not _still_signed_in(device.session, user)]
    if signed_out:
        Session.objects.filter(pk__in=[device.session_id for device in signed_out]).delete()

    return [device for device in devices if device not in signed_out]


def sign_out_device(device: DeviceSession) -> None:
    Session.objects.filter(pk=device.session_id).delete()


def sign_out_other_devices(user: User, *, keep: str) -> int:
    """Signs out every session of the account but `keep`. Returns how many.

    Sessions without a device row -- none are expected, but a gap in the
    recording must not leave one behind -- are found by what they hold.
    """
    listed = DeviceSession.objects.filter(user=user).exclude(session_id=keep)
    keys = set(listed.values_list("session_id", flat=True))

    unlisted = Session.objects.filter(expire_date__gt=timezone.now(), device__isnull=True).exclude(
        pk=keep
    )
    for session in unlisted.iterator():
        if session.get_decoded().get("_auth_user_id") == str(user.pk):
            keys.add(session.pk)

    _, removed = Session.objects.filter(pk__in=keys).delete()
    return removed.get("sessions.Session", 0)
