"""Import .docx, .txt and .md files into DocuGen's Markdown-subset format."""
from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.hyperlink import Hyperlink
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from services.formatting import clean_text

MAX_IMPORT_BYTES = 5 * 1024 * 1024
SUPPORTED = (".docx", ".txt", ".md", ".markdown")


class ImportErrorMessage(ValueError):
    """Raised with a user-friendly message when a file cannot be imported."""


def _wrap(text: str, marker: str) -> str:
    stripped = text.strip()
    if not stripped:
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    return f"{lead}{marker}{stripped}{marker}{trail}"


def _paragraph_markdown(paragraph: Paragraph) -> str:
    groups: list[list] = []                    # merge neighbouring runs with identical formatting
    for item in paragraph.iter_inner_content():
        runs = item.runs if isinstance(item, Hyperlink) else [item]
        for run in runs:
            if not isinstance(run, Run) or not run.text:
                continue
            key = (bool(run.bold), bool(run.italic))
            if groups and groups[-1][0] == key:
                groups[-1][1] += run.text
            else:
                groups.append([key, run.text])
    out = []
    for (bold, italic), text in groups:
        text = text.replace("*", "\\*").replace("\n", " ").replace("\t", " ")
        out.append(_wrap(text, "***" if bold and italic else "**" if bold else "*" if italic else ""))
    return "".join(out).strip()


def _list_info(paragraph: Paragraph, doc) -> tuple[str, int] | None:
    """Return ("bullet"|"number", level) for list paragraphs, else None."""
    name = paragraph.style.name if paragraph.style is not None else ""
    match = re.match(r"List (Bullet|Number)(?: (\d))?$", name)
    if match:
        level = int(match.group(2)) - 1 if match.group(2) else 0
        return ("bullet" if match.group(1) == "Bullet" else "number", min(level, 2))
    ppr = paragraph._p.pPr
    num_pr = ppr.numPr if ppr is not None else None
    if num_pr is None or num_pr.numId is None:
        return None
    level = int(num_pr.ilvl.val) if num_pr.ilvl is not None else 0
    kind = "bullet"
    try:
        numbering = doc.part.numbering_part.element
        num_id = str(num_pr.numId.val)
        for num in numbering.findall("{*}num"):
            if num.get("{*}numId") == num_id:
                abstract_id = num.find("{*}abstractNumId").get("{*}val")
                for abstract in numbering.findall("{*}abstractNum"):
                    if abstract.get("{*}abstractNumId") == abstract_id:
                        for lvl in abstract.findall("{*}lvl"):
                            if lvl.get("{*}ilvl") == str(level):
                                fmt = lvl.find("{*}numFmt")
                                if fmt is not None and fmt.get("{*}val") != "bullet":
                                    kind = "number"
    except Exception:  # unusual numbering definitions: default to bullet
        pass
    return kind, min(level, 2)


def _table_markdown(table: Table) -> str:
    rows = []
    for r, row in enumerate(table.rows):
        cells = []
        for cell in row.cells:
            text = " ".join(_paragraph_markdown(p) for p in cell.paragraphs).strip().replace("|", "/")
            if r == 0 and text.startswith("**") and text.endswith("**") and len(text) > 4:
                text = text[2:-2]                         # header rows are bold by convention
            cells.append(text)
        rows.append("| " + " | ".join(cells) + " |")
    if not rows:
        return ""
    width = len(table.rows[0].cells)
    rows.insert(1, "| " + " | ".join("---" for _ in range(width)) + " |")
    return "\n".join(rows)


def _import_docx(data: bytes, fallback_title: str) -> dict:
    try:
        doc = Document(BytesIO(data))
    except Exception as exc:
        raise ImportErrorMessage("That file is not a valid Word (.docx) document.") from exc
    title = ""
    pieces: list[tuple[str, str]] = []         # (kind, text)
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "tbl":
            text = _table_markdown(Table(child, doc))
            if text:
                pieces.append(("table", text))
        elif tag == "p":
            paragraph = Paragraph(child, doc)
            text = _paragraph_markdown(paragraph)
            ppr = paragraph._p.pPr
            if not text:
                if ppr is not None and ppr.find(qn("w:pBdr")) is not None:
                    pieces.append(("rule", "---"))        # empty paragraph with a border = rule
                continue
            style = paragraph.style.name if paragraph.style is not None else ""
            heading = re.match(r"Heading (\d)$", style)
            info = _list_info(paragraph, doc)
            if style == "Title":
                title = title or re.sub(r"[*\\]", "", text)
                continue
            if heading:
                level = min(int(heading.group(1)), 3)
                if not title and level == 1:
                    title = re.sub(r"[*\\]", "", text)
                pieces.append(("heading", "#" * level + " " + text))
            elif info:
                kind, level = info
                marker = "1. " if kind == "number" else "- "
                pieces.append(("list", "  " * level + marker + text))
            elif (typed := re.match(r"^\d+[.)]\s+(.+)$", text)):
                indent = paragraph.paragraph_format.left_indent
                level = 0 if indent is None else max(0, min(2, round((indent.inches - 0.5) / 0.25)))
                pieces.append(("list", "  " * level + "1. " + typed.group(1)))
            else:
                pieces.append(("paragraph", text))
    out: list[str] = []
    previous = None
    for kind, text in pieces:
        if out:
            out.append("\n" if (kind == "list" and previous == "list") else "\n\n")
        out.append(text)
        previous = kind
    return {"title": title or fallback_title, "content": "".join(out)}


def _decode_text(data: bytes) -> str:
    encodings = ["utf-8-sig"]
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):         # UTF-16 only when it has a byte-order mark
        encodings.append("utf-16")
    encodings.append("cp1252")
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeError:
            continue
    raise ImportErrorMessage("Could not read the text in that file.")


def import_file(filename: str, data: bytes) -> dict:
    """Convert an uploaded file to {"title": ..., "content": ...}."""
    ext = Path(filename or "").suffix.lower()
    stem = Path(filename or "Imported document").stem.strip() or "Imported document"
    if ext not in SUPPORTED:
        raise ImportErrorMessage(f"Unsupported file type. Supported: {', '.join(SUPPORTED)}")
    if len(data) > MAX_IMPORT_BYTES:
        raise ImportErrorMessage("That file is too large (maximum 5 MB).")
    if not data:
        raise ImportErrorMessage("That file is empty.")
    if ext == ".docx":
        return _import_docx(data, stem)
    text = clean_text(_decode_text(data))
    title = stem
    first = next((ln for ln in text.split("\n") if ln.strip()), "")
    match = re.match(r"^#\s+(.+?)\s*#*$", first)
    if ext != ".txt" and match:
        title = match.group(1)
    return {"title": title[:200], "content": text}
