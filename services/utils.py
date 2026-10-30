"""Small helpers shared by the app and export services."""
from __future__ import annotations

import re
import unicodedata

_RESERVED = {"CON", "PRN", "AUX", "NUL",
             *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_filename(title: str, ext: str = "", max_len: int = 80) -> str:
    """Return a filesystem-safe filename (safe on Windows, macOS and Linux)."""
    name = unicodedata.normalize("NFKC", title or "")
    name = re.sub(r"[^\w\- ]+", "_", name, flags=re.UNICODE)
    name = re.sub(r"[\s_]+", "_", name).strip("._- ")
    name = name[:max_len].strip("._- ")
    if not name or name.upper() in _RESERVED:
        name = "document"
    return f"{name}.{ext.lstrip('.')}" if ext else name
