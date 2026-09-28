"""Inspection and preparation of uploaded attachments.

Neither the file extension nor the browser-supplied `Content-Type` is trusted:
both are attacker-controlled. An image has to survive being decoded by Pillow
and an audio file has to be recognised by ffprobe before anything is stored.

Images are re-encoded on the way in. That drops every metadata block --
notably the GPS coordinates a phone camera writes -- while baking the EXIF
orientation into the pixels so the picture is not shown sideways.
"""

import json
import subprocess
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import serializers

from core.formatting import to_persian_digits

# Pillow format name -> the extension and MIME type used for storage.
ALLOWED_IMAGE_FORMATS: dict[str, tuple[str, str]] = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}

# ffprobe codec name -> the extension and MIME type used for storage. The
# container is what ffprobe reports in `format_name`, so the mapping is keyed
# on the audio codec instead, which is stable across containers.
ALLOWED_AUDIO_CODECS: dict[str, tuple[str, str]] = {
    "mp3": (".mp3", "audio/mpeg"),
    "aac": (".m4a", "audio/mp4"),
    "opus": (".ogg", "audio/ogg"),
    "vorbis": (".ogg", "audio/ogg"),
    "flac": (".flac", "audio/flac"),
    "pcm_s16le": (".wav", "audio/wav"),
    "pcm_s24le": (".wav", "audio/wav"),
}

# The formats by the names people know them by, for messages and for the
# upload hints in the interface (see core.views.SiteView).
IMAGE_FORMAT_NAMES = ("JPEG", "PNG", "WebP")
AUDIO_FORMAT_NAMES = ("MP3", "M4A", "OGG", "FLAC", "WAV")


def persian_list(names: tuple[str, ...]) -> str:
    """JPEG، PNG یا WebP"""
    return "، ".join(names[:-1]) + " یا " + names[-1]


IMAGE_FORMATS_TEXT = persian_list(IMAGE_FORMAT_NAMES)
AUDIO_FORMATS_TEXT = persian_list(AUDIO_FORMAT_NAMES)

# Guards against a decompression bomb: a small file that expands into an
# image large enough to exhaust memory.
Image.MAX_IMAGE_PIXELS = 64_000_000

FFPROBE_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class PreparedImage:
    content: ContentFile
    thumbnail: ContentFile
    extension: str
    content_type: str
    width: int
    height: int


@dataclass(frozen=True)
class PreparedAudio:
    extension: str
    content_type: str
    duration_ms: int


def _reject(message: str) -> None:
    raise serializers.ValidationError(message)


def human_megabytes(value: int) -> str:
    return to_persian_digits(f"{value / (1024 * 1024):.0f}")


def check_size(upload: UploadedFile, *, limit: int, label: str) -> None:
    if upload.size is None:
        _reject("حجم فایل قابل تشخیص نیست.")
    if upload.size > limit:
        _reject(f"حجم {label} نباید از {human_megabytes(limit)} مگابایت بیشتر باشد.")


def open_image(upload: UploadedFile, *, limit: int, label: str) -> tuple[Image.Image, str]:
    """Checks an upload really is an allowed image and decodes it.

    Returns the image upright and without its metadata, with its Pillow
    format. Shared by attachments and the profile picture.
    """
    check_size(upload, limit=limit, label=label)

    upload.seek(0)
    try:
        # `verify` catches truncated and malformed files, but leaves the image
        # object unusable, so the file has to be opened a second time.
        Image.open(upload).verify()
        upload.seek(0)
        image = Image.open(upload)
        image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        _reject(f"این فایل عکس معتبری نیست؛ فقط {IMAGE_FORMATS_TEXT} پذیرفته می‌شود.")

    image_format = image.format
    if image_format not in ALLOWED_IMAGE_FORMATS:
        _reject(f"فقط عکس با فرمت {IMAGE_FORMATS_TEXT} پذیرفته می‌شود.")

    # Applies the EXIF orientation to the pixels and returns an image with no
    # EXIF block, so the rotation survives and the metadata does not.
    image = ImageOps.exif_transpose(image)

    if image_format == "JPEG" and image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    return image, image_format


def prepare_image(upload: UploadedFile) -> PreparedImage:
    """Validates an image and returns the re-encoded original and thumbnail."""
    image, image_format = open_image(upload, limit=settings.MAX_IMAGE_UPLOAD_BYTES, label="عکس")
    extension, content_type = ALLOWED_IMAGE_FORMATS[image_format]

    original = encode_image(image, image_format)
    thumbnail_image = image.copy()
    thumbnail_image.thumbnail(settings.ATTACHMENT_THUMBNAIL_SIZE, Image.LANCZOS)
    thumbnail = encode_image(thumbnail_image, image_format)

    return PreparedImage(
        content=original,
        thumbnail=thumbnail,
        extension=extension,
        content_type=content_type,
        width=image.width,
        height=image.height,
    )


def encode_image(image: Image.Image, image_format: str) -> ContentFile:
    buffer = BytesIO()
    options: dict[str, Any] = {"format": image_format}

    if image_format == "JPEG":
        options.update(quality=90, optimize=True, progressive=True)
    elif image_format == "WEBP":
        options.update(quality=90, method=4)
    elif image_format == "PNG":
        options.update(optimize=True)

    image.save(buffer, **options)
    return ContentFile(buffer.getvalue())


def prepare_audio(upload: UploadedFile) -> PreparedAudio:
    """Validates an audio file with ffprobe and reads its duration."""
    check_size(upload, limit=settings.MAX_AUDIO_UPLOAD_BYTES, label="فایل صوتی")

    probe = _probe(upload)
    streams = probe.get("streams") or []

    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    if not audio_streams:
        _reject("این فایل صدا ندارد.")

    # Cover art is stored as a still video stream; a genuine video track is
    # not, and a video file must not slip in through the audio endpoint.
    video_streams = [
        s
        for s in streams
        if s.get("codec_type") == "video" and (s.get("disposition") or {}).get("attached_pic") != 1
    ]
    if video_streams:
        _reject("فایل ویدئویی پشتیبانی نمی‌شود؛ فقط عکس و صدا.")

    codec = audio_streams[0].get("codec_name")
    if codec not in ALLOWED_AUDIO_CODECS:
        _reject(f"این قالب صوتی پشتیبانی نمی‌شود؛ فقط {AUDIO_FORMATS_TEXT}.")

    extension, content_type = ALLOWED_AUDIO_CODECS[codec]

    raw_duration = (probe.get("format") or {}).get("duration")
    try:
        duration_ms = round(float(raw_duration) * 1000)
    except (TypeError, ValueError):
        duration_ms = 0

    if duration_ms <= 0:
        _reject("مدت فایل صوتی قابل تشخیص نیست.")

    return PreparedAudio(
        extension=extension,
        content_type=content_type,
        duration_ms=duration_ms,
    )


def _probe(upload: UploadedFile) -> dict[str, Any]:
    """Runs ffprobe against the upload.

    The bytes are written to a temporary file rather than piped: several
    container formats need to seek, and ffprobe cannot seek a pipe.
    """
    suffix = Path(upload.name or "").suffix[:10]

    with tempfile.NamedTemporaryFile(suffix=suffix) as handle:
        upload.seek(0)
        for chunk in upload.chunks():
            handle.write(chunk)
        handle.flush()
        upload.seek(0)

        try:
            completed = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    handle.name,
                ],
                capture_output=True,
                timeout=FFPROBE_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            _reject("پردازش فایل صوتی ناموفق بود.")

    if completed.returncode != 0:
        _reject(f"این فایل صوتی معتبری نیست؛ فقط {AUDIO_FORMATS_TEXT} پذیرفته می‌شود.")

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        _reject("پردازش فایل صوتی ناموفق بود.")
        return {}  # unreachable; keeps the return type honest
