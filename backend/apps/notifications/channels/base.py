"""The contract every delivery channel implements.

A channel takes an already-rendered message and gets it to the user. It does
not decide what to say, when to say it, or whether it has been said before --
those belong to the reminder engine.
"""

from dataclasses import dataclass
from typing import Protocol

from apps.ideas.models import Idea
from apps.users.models import User


@dataclass(frozen=True)
class Message:
    """What to deliver, already rendered in Persian."""

    recipient: User
    text: str
    idea: Idea | None = None


class ChannelUnavailableError(RuntimeError):
    """The channel cannot deliver right now.

    Raised for a missing configuration or an unlinked account -- a condition
    of the channel, not a failure of the message. The caller records the
    delivery as failed and moves on rather than retrying forever.
    """


class Channel(Protocol):
    name: str

    def is_available_for(self, user: User) -> bool:
        """Whether this user can currently be reached over the channel."""
        ...

    def send(self, message: Message) -> None:
        """Delivers the message, or raises ChannelUnavailableError."""
        ...
