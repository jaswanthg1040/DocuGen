"""Generate valid PDF files with ReportLab."""
from __future__ import annotations

import os
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from services.formatting import clean_text, parse_blocks

EMPTY_NOTICE = "This document is empty."
PAGE_SIZES = {"A4": A4, "Letter": letter}
MARGIN_X = 0.95 * inch

_FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
_WIN = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
# (regular, bold, italic, bold-italic); the first complete set found is used.
_FONT_SETS = [
    tuple(os.path.join(_WIN, f) for f in ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf")),
    tuple(str(_FONT_DIR / f) for f in
          ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf")),
    tuple(f"/usr/share/fonts/truetype/liberation/{f}" for f in
          ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf",
           "LiberationSans-Italic.ttf", "LiberationSans-BoldItalic.ttf")),
]


@lru_cache(maxsize=1)
def _fonts() -> tuple[str, bool]:
    """Register a Unicode TrueType family.

    Returns (font_family_name, unicode_ok). Falls back to built-in Helvetica
    (Western European only) if no usable TrueType set can be loaded.
    """
    for paths in _FONT_SETS:
        if all(os.path.exists(p) for p in paths):
            try:
                names = ("DocuGenSans", "DocuGenSans-Bold", "DocuGenSans-Italic", "DocuGenSans-BoldItalic")
                for name, path in zip(names, paths):
                    pdfmetrics.registerFont(TTFont(name, path))
                pdfmetrics.registerFontFamily(
                    names[0], normal=names[0], bold=names[1], italic=names[2], boldItalic=names[3])
                return names[0], True
            except Exception:  # corrupt font file: try the next set
                continue
    return "Helvetica", False


def _prepare(text: str, unicode_ok: bool) -> str:
    if not unicode_ok:
        text = text.encode("cp1252", "replace").decode("cp1252")
    return escape(text)


def _markup(runs, unicode_ok: bool) -> str:
    parts = []
    for text, bold, italic in runs:
        piece = _prepare(text, unicode_ok)
        if bold:
            piece = f"<b>{piece}</b>"
        if italic:
            piece = f"<i>{piece}</i>"
        parts.append(piece)
    return "".join(parts)


def _bold_name(font: str) -> str:
    return "Helvetica-Bold" if font == "Helvetica" else f"{font}-Bold"


def _styles(font: str) -> dict[str, ParagraphStyle]:
    ink = colors.HexColor("#1f2937")
    base = dict(fontName=font, textColor=ink, alignment=TA_LEFT, splitLongWords=1)
    head = dict(base, fontName=_bold_name(font))
    return {
        "title": ParagraphStyle("t", fontSize=24, leading=30, spaceAfter=6, fontName=_bold_name(font),
                                textColor=colors.HexColor("#3730a3"), splitLongWords=1),
        "desc": ParagraphStyle("d", fontSize=12, leading=16, spaceAfter=8, textColor=colors.HexColor("#6b7280"),
                               fontName=font, splitLongWords=1),
        "h1": ParagraphStyle("h1", fontSize=18, leading=23, spaceBefore=14, spaceAfter=6, keepWithNext=1, **head),
        "h2": ParagraphStyle("h2", fontSize=15, leading=20, spaceBefore=12, spaceAfter=5, keepWithNext=1, **head),
        "h3": ParagraphStyle("h3", fontSize=13, leading=17, spaceBefore=10, spaceAfter=4, keepWithNext=1, **head),
        "body": ParagraphStyle("b", fontSize=11, leading=15.5, spaceAfter=8, **base),
        "cell": ParagraphStyle("c", fontSize=10, leading=13.5, **base),
        "empty": ParagraphStyle("e", fontSize=11, leading=15, textColor=colors.HexColor("#9ca3af"), fontName=font),
    }


def _list_style(font: str, level: int) -> ParagraphStyle:
    return ParagraphStyle(f"l{level}", fontSize=11, leading=15.5, spaceAfter=3, fontName=font,
                          textColor=colors.HexColor("#1f2937"), splitLongWords=1,
                          leftIndent=26 + 18 * level, bulletIndent=6 + 18 * level, bulletFontName=font)


def _table(rows, styles, unicode_ok: bool, available_width: float) -> Table:
    data = []
    for r, row in enumerate(rows):
        cells = []
        for cell in row:
            text = _markup(cell, unicode_ok)
            cells.append(Paragraph(f"<b>{text}</b>" if (r == 0 and text) else (text or "&nbsp;"), styles["cell"]))
        data.append(cells)
    table = Table(data, colWidths=[available_width / len(rows[0])] * len(rows[0]), repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#c7d2fe")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e7ff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def build_pdf(title: str, content: str, description: str = "", include_description: bool = True,
              page_size: str = "A4", page_numbers: bool = True) -> bytes:
    """Return the bytes of a PDF document for the given title and content."""
    title = clean_text(title).strip() or "Untitled document"
    description = clean_text(description).strip()
    font, unicode_ok = _fonts()
    styles = _styles(font)
    pagesize = PAGE_SIZES.get(page_size, A4)
    available = pagesize[0] - 2 * MARGIN_X - 12   # frames keep 6pt padding per side

    story = [Paragraph(_prepare(title, unicode_ok), styles["title"])]
    if include_description and description:
        story.append(Paragraph(_prepare(description, unicode_ok), styles["desc"]))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c7d2fe"),
                            spaceBefore=4, spaceAfter=12))

    blocks = parse_blocks(content)
    if not blocks:
        story.append(Paragraph(f"<i>{EMPTY_NOTICE}</i>", styles["empty"]))
    for block in blocks:
        if block.kind == "heading":
            story.append(Paragraph(_markup(block.lines[0], unicode_ok), styles[f"h{block.level}"]))
        elif block.kind == "bullet":
            story.append(Paragraph(_markup(block.lines[0], unicode_ok), _list_style(font, block.level),
                                   bulletText="\u2022"))
        elif block.kind == "number":
            story.append(Paragraph(_markup(block.lines[0], unicode_ok), _list_style(font, block.level),
                                   bulletText=f"{block.number}."))
        elif block.kind == "rule":
            story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#c7d2fe"),
                                    spaceBefore=6, spaceAfter=10))
        elif block.kind == "table":
            story.append(_table(block.rows, styles, unicode_ok, available))
            story.append(Spacer(1, 10))
        else:
            text = "<br/>".join(_markup(line, unicode_ok) for line in block.lines)
            story.append(Paragraph(text, styles["body"]))
    story.append(Spacer(1, 6))

    def footer(canvas, doc):
        if not page_numbers:
            return
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#9ca3af"))
        canvas.drawCentredString(pagesize[0] / 2, 0.5 * inch, f"Page {doc.page}")
        canvas.restoreState()

    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer, pagesize=pagesize, title=title[:250], author="DocuGen",
        leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=0.9 * inch, bottomMargin=0.95 * inch,
    )
    pdf.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
