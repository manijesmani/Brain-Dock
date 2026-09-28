"""Delivery of private files: attachments and the profile picture.

MEDIA_ROOT is never published by the web server. A view first decides that
the requester may have the file, and only then is it sent.
"""

from urllib.parse import quote

from django.conf import settings
from django.db.models.fields.files import FieldFile
from django.http import FileResponse, HttpResponse


def private_file_response(
    *, file_field: FieldFile, content_type: str, filename: str
) -> HttpResponse:
    """Sends a file the caller has already checked access to.

    In production the bytes are handed to Nginx via X-Accel-Redirect, so
    Python is not tied up streaming them; the location it names is declared
    `internal` and cannot be requested directly.
    """
    if settings.DEBUG:
        # No Nginx in front of the development server, so Django serves the
        # bytes itself.
        return FileResponse(file_field.open("rb"), content_type=content_type)

    response = HttpResponse(content_type=content_type)
    response["X-Accel-Redirect"] = f"{settings.MEDIA_INTERNAL_URL}{quote(file_field.name)}"
    # The name may be Persian, so it is sent in the RFC 5987 form only.
    response["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(filename)}"
    return response
