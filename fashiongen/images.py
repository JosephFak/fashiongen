"""Decode and normalize user images without retaining metadata or files."""

import base64
import binascii
import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PIXELS = 25_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def decode_image(value: str, max_bytes: int) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("Choose an image before searching.")
    if value.startswith("data:"):
        header, separator, value = value.partition(",")
        if not separator or header not in {
            "data:image/png;base64", "data:image/jpeg;base64", "data:image/webp;base64"
        }:
            raise ValueError("Use a PNG, JPEG, or WebP image.")
    if len(value) > ((max_bytes + 2) // 3) * 4:
        raise ValueError("Images must be 10 MB or smaller.")
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("The image could not be decoded. Please choose it again.") from exc
    return normalize_image(data, max_bytes)


def normalize_image(data: bytes, max_bytes: int) -> bytes:
    if not data or len(data) > max_bytes:
        raise ValueError("Images must be nonempty and 10 MB or smaller.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as original:
                if original.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValueError("Use a PNG, JPEG, or WebP image.")
                if original.width * original.height > MAX_PIXELS:
                    raise ValueError("Use an image smaller than 25 megapixels.")
                image = ImageOps.exif_transpose(original).convert("RGBA")
                image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                # Flatten transparency onto white; create a fresh image to discard EXIF.
                background = Image.new("RGB", image.size, "white")
                background.paste(image, mask=image.getchannel("A"))
                output = io.BytesIO()
                background.save(output, format="JPEG", quality=92)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValueError("This image is damaged, unsupported, or too large to process.") from exc
