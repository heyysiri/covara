"""Upload validation helpers. Uploaded files are untrusted input."""

import re
from pathlib import PurePosixPath, PureWindowsPath

# extension -> (canonical content type, magic-byte prefixes)
ALLOWED_TYPES: dict[str, tuple[str, tuple[bytes, ...]]] = {
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
}

_UNSAFE = re.compile(r"[^\w.\- ()]+", re.UNICODE)


def display_filename(raw: str | None) -> str:
    """Return a sanitized filename safe to show/store as metadata (never used as a path)."""
    name = PureWindowsPath(PurePosixPath(raw or "").name).name
    name = _UNSAFE.sub("_", name).strip(" .")
    return (name or "document")[:200]


def extension_of(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def validate_signature(ext: str, head: bytes) -> bool:
    """Check the file's leading bytes match its claimed extension."""
    _, signatures = ALLOWED_TYPES[ext]
    return any(head.startswith(sig) for sig in signatures)
