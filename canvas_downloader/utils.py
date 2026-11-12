"""Shared helpers: errors, filename sanitization, path safety, hashing."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

MEDIA_EXTENSIONS = {
    ".mp4", ".webm", ".ogg", ".mov", ".m4v", ".mp3", ".wav", ".m4a",
    ".pdf", ".ppt", ".pptx", ".doc", ".docx", ".xls", ".xlsx", ".zip",
}
RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
}


class CanvasError(RuntimeError):
    """Raised for any unrecoverable Canvas API or transport failure."""


def safe_name(value: object, fallback: str = "untitled", limit: int = 150) -> str:
    """Sanitize one filename/folder component for Windows, macOS and Linux."""
    name = unicodedata.normalize("NFKC", str(value or "")).strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if name in {"", ".", ".."}:
        name = fallback
    if name.split(".", 1)[0].upper() in RESERVED:
        name = "_" + name
    return name[:limit].rstrip(" .") or fallback


def under_root(root: Path, *parts: str) -> Path:
    """Join sanitized parts under root, refusing any path that escapes it."""
    root = root.resolve()
    result = root.joinpath(*(safe_name(p) for p in parts)).resolve()
    if result != root and root not in result.parents:
        raise ValueError("Refusing to write outside the output directory")
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
