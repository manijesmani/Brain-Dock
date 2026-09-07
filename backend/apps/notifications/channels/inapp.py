"""Delivery into the notification centre.

Always available: it writes a row the user sees the next time they open the
app, so there is nothing to configure and nothing that can be unreachable.
"""

from apps.notifications.channels.base import Message
from apps.notifications.models import Notification, NotificationKind
from apps.users.models import User


class InAppChannel:
    name = "inapp"

    def __init__(self, kind: str = NotificationKind.REMINDER) -> None:
        self.kind = kind

    def is_available_for(self, user: User) -> bool:
        return True

    def send(self, message: Message) -> Notification:
        return Notification.objects.create(
            owner=message.recipient,
            kind=self.kind,
            text=message.text,
            idea=message.idea,
        )
