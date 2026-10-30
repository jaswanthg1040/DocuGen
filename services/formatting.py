"""Markdown-subset parser shared by the preview and every export format.

Supported syntax (one source of truth for every output):
    # Heading 1 / ## Heading 2 / ### Heading 3
    - bullet item   (also * or +)       1. numbered item
      (indent a list item by 2 spaces per level, up to 3 levels)
    **bold**, *italic*, ***bold italic***      \\*  for a literal asterisk
    | Column A | Column B |     tables: the first row is the header
    | cell     | cell     |     (a |---|---| separator row is optional)
    ---                         horizontal rule
    Blank line = new paragraph. A single line break inside a paragraph is kept.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

Run = tuple[str, bool, bool]  # (text, bold, italic)

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")
_INLINE = re.compile(
    r"\*\*\*(?P<bi>.+?)\*\*\*|\*\*(?P<b>.+?)\*\*|\*(?P<i>[^\s*](?:.*?[^\s*])?)\*"
)
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_BULLET = re.compile(r"^(\s*)[-*+\u2022]\s+(.+)$")
_NUMBER = re.compile(r"^(\s*)\d+[.)]\s+(.+)$")
_RULE = re.compile(r"^(-{3,}|\*{3,}|_{3,})$")
_SEPARATOR_CELL = re.compile(r":?-+:?")
_MD_ESCAPE = re.compile(r"([\\`*_{}\[\]<>#|~$&])")
_LITERAL_STAR = "\ue000"
MAX_LIST_LEVEL = 2


@dataclass
class Block:
    kind: str                       # heading | paragraph | bullet | number | table | rule
    lines: list[list[Run]] = field(default_factory=list)
    level: int = 0                  # heading level 1-3, or list nesting depth 0-2
    number: int = 0                 # item number for "number" blocks
    rows: list[list[list[Run]]] = field(default_factory=list)   # table rows -> cells -> runs


def clean_text(text: str | None) -> str:
    """Normalise newlines and strip characters that are invalid in XML/Word."""
    return _CONTROL.sub("", (text or "").replace("\r\n", "\n").replace("\r", "\n"))


def parse_inline(text: str, bold: bool = False, italic: bool = False) -> list[Run]:
    runs: list[Run] = []
    pos = 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            runs.append((text[pos:m.start()], bold, italic))
        if m.group("bi") is not None:
            runs.extend(parse_inline(m.group("bi"), True, True))
        elif m.group("b") is not None:
            runs.extend(parse_inline(m.group("b"), True, italic))
        else:
            runs.extend(parse_inline(m.group("i"), bold, True))
        pos = m.end()
    if pos < len(text):
        runs.append((text[pos:], bold, italic))
    return runs


def _inline(text: str) -> list[Run]:
    """parse_inline with support for \\* as a literal asterisk."""
    runs = parse_inline(text.replace("\\*", _LITERAL_STAR))
    return [(t.replace(_LITERAL_STAR, "*"), b, i) for t, b, i in runs]


def _parse_table(rows_text: list[str]) -> list[list[list[Run]]]:
    rows: list[list[str]] = []
    for line in rows_text:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if rows and cells and all(_SEPARATOR_CELL.fullmatch(c) for c in cells):
            continue                                      # |---|---| separator row
        rows.append(cells)
    if not rows:
        return []
    width = max(len(r) for r in rows)
    return [[_inline(c) for c in r + [""] * (width - len(r))] for r in rows]


def parse_blocks(content: str | None) -> list[Block]:
    blocks: list[Block] = []
    paragraph: list[list[Run]] = []
    counters = [0, 0, 0]

    def reset_counters() -> None:
        counters[:] = [0, 0, 0]

    def flush() -> None:
        if paragraph:
            blocks.append(Block("paragraph", list(paragraph)))
            paragraph.clear()
            reset_counters()

    lines = clean_text(content).split("\n")
    i = 0
    while i < len(lines):
        raw = lines[i].expandtabs(4).rstrip()
        stripped = raw.strip()
        if not stripped:
            flush()
            i += 1
        elif _RULE.match(stripped):
            flush()
            blocks.append(Block("rule"))
            reset_counters()
            i += 1
        elif stripped.startswith("|"):
            flush()
            j = i
            table_lines = []
            while j < len(lines) and lines[j].strip().startswith("|"):
                table_lines.append(lines[j])
                j += 1
            rows = _parse_table(table_lines)
            if rows:
                blocks.append(Block("table", rows=rows))
                reset_counters()
            i = j
        elif (m := _HEADING.match(raw)):
            flush()
            blocks.append(Block("heading", [_inline(m.group(2))], level=min(len(m.group(1)), 3)))
            reset_counters()
            i += 1
        elif (m := _BULLET.match(raw)):
            flush()
            level = min(len(m.group(1)) // 2, MAX_LIST_LEVEL)
            counters[level:] = [0] * (3 - level)
            blocks.append(Block("bullet", [_inline(m.group(2))], level=level))
            i += 1
        elif (m := _NUMBER.match(raw)):
            flush()
            level = min(len(m.group(1)) // 2, MAX_LIST_LEVEL)
            counters[level] += 1
            counters[level + 1:] = [0] * (2 - level)
            blocks.append(Block("number", [_inline(m.group(2))], level=level, number=counters[level]))
            i += 1
        else:
            paragraph.append(_inline(stripped))
            i += 1
    flush()
    return blocks


# ------------------------------------------------------------------ plain text / stats
def runs_text(runs: list[Run]) -> str:
    return "".join(t for t, _, _ in runs)


def block_text(block: Block) -> str:
    """Plain text of a block (no markup)."""
    if block.kind == "table":
        return "\n".join(" | ".join(runs_text(c) for c in row) for row in block.rows)
    return "\n".join(runs_text(line) for line in block.lines)


def count_stats(content: str | None) -> dict:
    """Words, characters (excluding markup) and estimated reading minutes."""
    text = "\n".join(block_text(b) for b in parse_blocks(content))
    words = len(text.split())
    return {"words": words, "characters": len(text), "minutes": math.ceil(words / 200) if words else 0}


# ------------------------------------------------------------------ preview
def escape_markdown(text: str | None) -> str:
    """Escape Markdown/LaTeX control characters in plain text."""
    return _MD_ESCAPE.sub(r"\\\1", clean_text(text))


def _wrap(text: str, marker: str) -> str:
    stripped = text.strip()
    if not stripped:
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    return f"{lead}{marker}{stripped}{marker}{trail}"


def _runs_to_markdown(runs: list[Run]) -> str:
    out = []
    for text, bold, italic in runs:
        piece = _MD_ESCAPE.sub(r"\\\1", text)
        if bold and italic:
            piece = _wrap(piece, "***")
        elif bold:
            piece = _wrap(piece, "**")
        elif italic:
            piece = _wrap(piece, "*")
        out.append(piece)
    return "".join(out)


def preview_markdown(content: str | None) -> str:
    """Render the supported subset to *escaped* Markdown for st.markdown().

    Everything the exporters do not support is escaped, so the preview closely
    matches the exported file and arbitrary HTML/links/images are never rendered.
    """
    parts: list[str] = []
    prev: Block | None = None
    for block in parse_blocks(content):
        if block.kind == "heading":
            text = "#" * block.level + " " + _runs_to_markdown(block.lines[0])
        elif block.kind == "bullet":
            text = "    " * block.level + "- " + _runs_to_markdown(block.lines[0])
        elif block.kind == "number":
            text = "    " * block.level + f"{block.number}. " + _runs_to_markdown(block.lines[0])
        elif block.kind == "rule":
            text = "---"
        elif block.kind == "table":
            rendered = ["| " + " | ".join(_runs_to_markdown(c) or " " for c in row) + " |" for row in block.rows]
            rendered.insert(1, "| " + " | ".join("---" for _ in block.rows[0]) + " |")
            text = "\n".join(rendered)
        else:
            text = "  \n".join(_runs_to_markdown(line) for line in block.lines)
        in_list = (prev is not None and prev.kind in ("bullet", "number")
                   and block.kind in ("bullet", "number"))
        if parts:
            parts.append("\n" if in_list else "\n\n")
        parts.append(text)
        prev = block
    return "".join(parts)
