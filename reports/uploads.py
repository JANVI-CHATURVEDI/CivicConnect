"""Upload validation: size, Pillow verify, EXIF GPS hint, strip, thumbnail."""

import io

from django.core.files.base import ContentFile
from PIL import Image
from PIL.ExifTags import TAGS

MAX_UPLOAD_MB = 5
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def validate_and_clean_image(uploaded):
    """Returns (cleaned_file, gps_hint(lat,lon)|None, error|None)."""
    if not uploaded:
        return None, None, None
    try:
        uploaded.seek(0)
        data = uploaded.read()
    except Exception:
        return None, None, "Could not read upload."
    if len(data) > MAX_UPLOAD_BYTES:
        return None, None, f"Image too large (max {MAX_UPLOAD_MB}MB)."
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
    except Exception:
        return None, None, "File is not a valid image."
    img = Image.open(io.BytesIO(data))  # reopen after verify
    if img.format not in ("JPEG", "PNG", "WEBP"):
        # allow conversion instead of reject for common types
        pass
    gps = _extract_gps(img)
    # strip EXIF by re-saving without exif
    try:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        cleaned = ContentFile(buf.getvalue(), name=getattr(uploaded, "name", "upload.jpg"))
    except Exception:
        return None, None, "Could not process image."
    return cleaned, gps, None


def make_thumbnail(image_field_file, size=(400, 400)):
    try:
        img = Image.open(image_field_file.path)
        img.thumbnail(size)
        buf = io.BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=70)
        return ContentFile(buf.getvalue())
    except Exception:
        return None


def _extract_gps(img):
    try:
        exif = img.getexif()
        if not exif:
            return None
        gps_info = None
        for tag_id, val in exif.items():
            if TAGS.get(tag_id) == "GPSInfo":
                gps_info = val
                break
        if not gps_info:
            return None

        def _d(v):
            d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
            return d

        lat = _d(gps_info[2]) * (-1 if gps_info.get(1) == "S" else 1)
        lon = _d(gps_info[4]) * (-1 if gps_info.get(3) == "W" else 1)
        return (lat, lon)
    except Exception:
        return None
