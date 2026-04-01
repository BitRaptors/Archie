"""Utility for cropping images around a detected face position."""

import io
from PIL import Image


def crop_image_by_face_x(
    image_bytes: bytes,
    face_x: float,
    crop_width_pct: float = 0.45,
    output_format: str = "JPEG",
    quality: int = 90,
) -> bytes:
    """Crop an image around a face's horizontal position.

    Args:
        image_bytes: Raw image bytes
        face_x: Horizontal center of face as percentage (0-100) from left
        crop_width_pct: Width of crop as fraction of original (0.0-1.0). Default 0.45 (45%)
        output_format: PIL image format for output
        quality: JPEG quality (1-100)

    Returns:
        Cropped image bytes
    """
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size

    center_x = int(w * face_x / 100)
    crop_w = max(int(w * crop_width_pct), 200)  # minimum 200px wide
    half = crop_w // 2

    left = max(0, center_x - half)
    right = min(w, center_x + half)

    # If we hit an edge, shift the other side
    if left == 0:
        right = min(w, crop_w)
    if right == w:
        left = max(0, w - crop_w)

    cropped = img.crop((left, 0, right, h))

    buf = io.BytesIO()
    # Convert RGBA to RGB for JPEG
    if cropped.mode in ("RGBA", "P"):
        cropped = cropped.convert("RGB")
    cropped.save(buf, format=output_format, quality=quality)
    return buf.getvalue()
