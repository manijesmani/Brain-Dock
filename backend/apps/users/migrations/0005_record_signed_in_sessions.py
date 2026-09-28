"""Lists the sessions already signed in when the device list came about.

Without this, a browser signed in before the deployment would be missing
from «دستگاه‌های فعال» until it next made a request -- and one that never
does, a lost phone for instance, could not be signed out from there. What
browser each one is was never written down, so they appear as an unknown
device until they are used again.
"""

from django.db import migrations
from django.utils import timezone


def record_signed_in_sessions(apps, schema_editor):
    from django.contrib.sessions.backends.db import SessionStore

    Session = apps.get_model("sessions", "Session")
    User = apps.get_model("users", "User")
    DeviceSession = apps.get_model("users", "DeviceSession")

    # Guests have no device list.
    accounts = set(User.objects.filter(is_guest=False).values_list("pk", flat=True))
    store = SessionStore()
    devices = []

    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        user_id = store.decode(session.session_data).get("_auth_user_id")
        if user_id is not None and int(user_id) in accounts:
            devices.append(DeviceSession(session_id=session.pk, user_id=int(user_id)))

    DeviceSession.objects.bulk_create(devices, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("sessions", "0001_initial"),
        ("users", "0004_devicesession"),
    ]

    operations = [
        migrations.RunPython(record_signed_in_sessions, migrations.RunPython.noop),
    ]
