"""Abstract model bases shared across the project.

Every concrete model inherits from one of these. `OwnedModel` in particular is
what keeps the multi-tenant guarantee honest: a model that carries user data
and does not inherit it is a bug.
"""

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Adds automatic creation and modification timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OwnedModel(models.Model):
    """Adds the owning user.

    The related name is derived from the concrete model so each subclass gets a
    readable reverse accessor without having to declare one.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(class)ss",
        db_index=True,
    )

    class Meta:
        abstract = True


class OwnedTimeStampedModel(OwnedModel, TimeStampedModel):
    """The combination almost every domain model needs."""

    class Meta:
        abstract = True
