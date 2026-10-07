"""Keeps stored files in step with the rows that reference them.

Deleting a model row does not remove the file a FileField points at, so
without this an attachment deleted through the API -- or removed by the
cascade when its idea is deleted -- would leave the bytes on disk forever.
"""

from typing import Any

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.ideas.models import Attachment


@receiver(post_delete, sender=Attachment)
def delete_attachment_files(sender: type[Attachment], instance: Attachment, **kwargs: Any) -> None:
    for field in (instance.file, instance.thumbnail):
        if field:
            # A failed account/idea deletion must leave its files intact.
            # Capture the path now; the model instance is no longer saved.
            transaction.on_commit(
                lambda storage=field.storage, name=field.name: storage.delete(name)
            )
