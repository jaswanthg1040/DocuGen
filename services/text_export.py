"""Plain-text and Markdown exports."""
from __future__ import annotations

from services.formatting import block_text, clean_text, parse_blocks


def to_markdown(title: str, content: str, description: str = "", include_description: bool = True) -> str:
    """Markdown file: title, optional description, then the document as written."""
    title = clean_text(title).strip() or "Untitled document"
    parts = [f"# {title}"]
    if include_description and clean_text(description).strip():
        parts.append(f"*{clean_text(description).strip()}*")
    body = clean_text(content).strip("\n")
    if body:
        parts.append(body)
    return "\n\n".join(parts) + "\n"


def to_text(title: str, content: str, description: str = "", include_description: bool = True) -> str:
    """Plain text file with simple bullets and numbering."""
    title = clean_text(title).strip() or "Untitled document"
    out = [title, "=" * min(len(title), 72)]
    if include_description and clean_text(description).strip():
        out += ["", clean_text(description).strip()]
    previous = None
    for block in parse_blocks(content):
        text = block_text(block)
        if block.kind == "bullet":
            text = "  " * block.level + "\u2022 " + text
        elif block.kind == "number":
            text = "  " * block.level + f"{block.number}. " + text
        elif block.kind == "rule":
            text = "-" * 40
        elif block.kind == "heading":
            text = text.upper() if block.level == 1 else text
        tight = previous in ("bullet", "number") and block.kind in ("bullet", "number")
        out += ([text] if tight else ["", text])
        previous = block.kind
    return "\n".join(out) + "\n"
