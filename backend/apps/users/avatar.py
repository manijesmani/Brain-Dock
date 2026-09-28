"""The profile picture: an image, cropped square and bounded in size.

It passes the same checks as an image attachment -- decoded for real,
turned upright, stripped of its metadata -- and is then cut to a centred
square, since it is only ever shown in a circle. The upload may be large, so a
photo straight off a phone is fine; what is kept is up to AVATAR_SIZE pixels
a side, well above what most sites keep, so it stays sharp on any screen.
"""

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps

from apps.ideas.attachments import ALLOWED_IMAGE_FORMATS, encode_image, open_image

# Extension -> MIME type, for sending the stored file back.
CONTENT_TYPES = dict(ALLOWED_IMAGE_FORMATS.values())


def prepare_avatar(upload: UploadedFile) -> tuple[ContentFile, str]:
    """Returns the re-encoded square picture and the extension to store it under."""
    image, image_format = open_image(
        upload, limit=settings.MAX_AVATAR_UPLOAD_BYTES, label="تصویر پروفایل"
    )

    # Palette and bilevel images only resize by nearest neighbour; converted
    # first, they scale smoothly like everything else.
    if image.mode not in ("RGB", "RGBA", "L"):
        image = image.convert("RGBA" if image_format != "JPEG" else "RGB")

    side = min(image.width, image.height, settings.AVATAR_SIZE)
    square = ImageOps.fit(image, (side, side), Image.LANCZOS)

    extension, _ = ALLOWED_IMAGE_FORMATS[image_format]
    return encode_image(square, image_format), extension
