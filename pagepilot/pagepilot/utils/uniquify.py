"""Media uniquifier: make uploads hash-unique without visible changes.

Video: appends a `uuid` MP4 box with 16 random bytes at the end of the file.
Players ignore unknown trailing boxes, but the file hash changes — this
defeats naive hash-based duplicate detection when re-uploading the same clip.

Image: Pillow re-encode with slightly different JPEG compression.

Both return the path of a NEW file in DATA_DIR/tmp (original untouched).
"""
import os
import struct
import uuid as _uuid

import config


def _tmp_out(src: str, suffix: str) -> str:
    d = os.path.join(config.DATA_DIR, "tmp")
    os.makedirs(d, exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0][:40]
    return os.path.join(d, f"{base}_uq_{_uuid.uuid4().hex[:8]}{suffix}")


def uniquify_video(src: str) -> str | None:
    if not os.path.exists(src):
        return None
    ext = os.path.splitext(src)[1] or ".mp4"
    out = _tmp_out(src, ext)
    # uuid box: size(4) + 'uuid'(4) + 16-byte user type + 16-byte payload = 40
    box = struct.pack(">I", 40) + b"uuid" + _uuid.uuid4().bytes + _uuid.uuid4().bytes
    try:
        with open(src, "rb") as f, open(out, "wb") as o:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                o.write(chunk)
            o.write(box)
        return out
    except Exception:
        try:
            os.remove(out)
        except Exception:
            pass
        return None


def uniquify_image(src: str) -> str | None:
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        out = _tmp_out(src, ".jpg")
        with Image.open(src) as im:
            im.convert("RGB").save(out, "JPEG", quality=94)
        return out
    except Exception:
        return None


def uniquify(src: str) -> str | None:
    """Uniquify any supported media file. Returns new path or None."""
    ext = os.path.splitext(src)[1].lower()
    if ext in (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".3gp"):
        return uniquify_video(src)
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
        return uniquify_image(src)
    return None
