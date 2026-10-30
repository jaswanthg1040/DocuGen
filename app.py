"""DocuGen 2 — AI Document Studio. Streamlit entry point.

Run with:  python -m streamlit run app.py
"""
from __future__ import annotations

from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import database as db  # noqa: E402
from components import ui  # noqa: E402
from services.formatting import count_stats, escape_markdown, preview_markdown  # noqa: E402
from services.importer import ImportErrorMessage, SUPPORTED, import_file  # noqa: E402
from services.pdf_export import build_pdf  # noqa: E402
from services.templates import TEMPLATES, get_template  # noqa: E402
from services.text_export import to_markdown, to_text  # noqa: E402
from services.utils import safe_filename  # noqa: E402
from services.word_export import build_docx  # noqa: E402

st.set_page_config(page_title="DocuGen — AI Document Studio", page_icon="📄", layout="wide")

VERSION = "2.0.0"
PAGE_DASH, PAGE_EDIT, PAGE_DOCS = "Dashboard", "Create Document", "My Documents"
PAGE_TPL, PAGE_SET, PAGE_HELP = "Templates", "Settings", "Help & About"
PAGES = [PAGE_DASH, PAGE_EDIT, PAGE_DOCS, PAGE_TPL, PAGE_SET, PAGE_HELP]
ICONS = {PAGE_DASH: "🏠", PAGE_EDIT: "✏️", PAGE_DOCS: "📚", PAGE_TPL: "🧩", PAGE_SET: "⚙️", PAGE_HELP: "❓"}

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SORT_OPTIONS = {"Recently modified": "recent", "Newest first": "newest",
                "Oldest first": "oldest", "Alphabetical (A–Z)": "az"}
THEME_MAP = {"Light": "light", "Dark": "dark"}
EXPORT_MAP = {"Word (.docx)": "docx", "PDF (.pdf)": "pdf"}
FONTS = ["Calibri", "Arial", "Times New Roman", "Cambria", "Georgia", "Verdana"]
PAGE_SIZES = ["A4", "Letter"]
ALL_TAGS = "All tags"
DEFAULT_SETTINGS = {"theme": "light", "default_export": "docx", "word_font": "Calibri",
                    "include_description": "1", "page_size": "A4", "page_numbers": "1"}
EDITOR_WIDGETS = (("w_title", "title"), ("w_desc", "description"),
                  ("w_tags", "tags"), ("w_content", "content"))
SNIPPETS = {
    "Heading": "# Heading", "Subheading": "## Subheading",
    "Bullets": "- First item\n- Second item", "Numbers": "1. First step\n2. Second step",
    "Table": "| Column A | Column B |\n| --- | --- |\n| Cell | Cell |",
    "Bold": "**bold text**", "Italic": "*italic text*", "Line": "---",
}

ss = st.session_state


# --------------------------------------------------------------------------- helpers
def fmt_dt(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value).strftime("%d %b %Y, %I:%M %p")
    except ValueError:
        return str(value)


def flash(kind: str, message: str) -> None:
    ss["flash"] = (kind, message)


def show_flash() -> None:
    item = ss.pop("flash", None)
    if item:
        kind, message = item
        {"success": st.success, "error": st.error, "warning": st.warning}.get(kind, st.info)(message)


def goto(page: str) -> None:
    """Request navigation. Safe to call from callbacks and page bodies."""
    ss["_goto"] = page


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    try:
        stored = db.get_all_settings()
    except db.DatabaseError:
        stored = {}
    settings.update({k: v for k, v in stored.items() if k in settings})
    if settings["theme"] not in THEME_MAP.values():
        settings["theme"] = "light"
    if settings["default_export"] not in EXPORT_MAP.values():
        settings["default_export"] = "docx"
    if settings["word_font"] not in FONTS:
        settings["word_font"] = "Calibri"
    if settings["page_size"] not in PAGE_SIZES:
        settings["page_size"] = "A4"
    return settings


def init_state() -> None:
    try:
        db.init_db()
    except db.DatabaseError as exc:
        st.error(f"DocuGen cannot open its database. {exc}\n\n"
                 "Check that the 'data' folder is writable (see README → Troubleshooting).")
        st.stop()
    if "settings" not in ss:
        ss["settings"] = load_settings()
    if "recover" not in ss:                              # unsaved work from a previous session
        ss["recover"] = None
        try:
            row = db.get_draft()
        except db.DatabaseError:
            row = None
        if row and (row["title"].strip() or row["content"].strip() or row["description"].strip()):
            ss["recover"] = row
    ss.setdefault("nav_page", PAGE_DASH)
    ss.setdefault("draft", blank_draft())
    ss.setdefault("imp_key", 0)
    for key in ("pending_load", "confirm_delete", "export_open", "view_id"):
        ss.setdefault(key, None)
    ss.setdefault("confirm_cancel", False)


# --------------------------------------------------------------------------- draft state
def blank_payload() -> dict:
    return {"doc_id": None, "title": "", "description": "", "tags": "", "content": "",
            "created_at": None, "updated_at": None}


def blank_draft() -> dict:
    return {**blank_payload(), "saved": ("", "", "", "")}


def load_draft(payload: dict, saved: tuple | None = None) -> None:
    """Replace the editor contents. Clears widget state so nothing stale leaks in."""
    p = {**blank_payload(), **payload}
    if saved is None:
        saved = ("", "", "", "") if p["doc_id"] is None else (
            p["title"], p["description"], p["tags"], p["content"])
    ss["draft"] = {**p, "saved": tuple(saved)}
    for key, _ in EDITOR_WIDGETS:
        ss.pop(key, None)
    ss["confirm_cancel"] = False


def sync_draft() -> None:
    """Copy current editor widget values into the draft (no-op if not rendered)."""
    for key, field in EDITOR_WIDGETS:
        if key in ss:
            ss["draft"][field] = ss[key]


def is_dirty() -> bool:
    d = ss["draft"]
    return (d["title"], d["description"], d["tags"], d["content"]) != tuple(d["saved"])


def open_in_editor(payload: dict) -> None:
    """Open a document/template in the editor, asking before discarding changes."""
    sync_draft()
    if is_dirty():
        ss["pending_load"] = payload
    else:
        load_draft(payload)
    goto(PAGE_EDIT)


def autosave() -> None:
    """Persist unsaved editor text so it can be recovered after a refresh or crash."""
    if ss.get("recover") is not None:       # wait until the user decides about the old draft
        return
    d = ss["draft"]
    snapshot = (d["doc_id"], d["title"], d["description"], d["tags"], d["content"]) if is_dirty() else None
    if ss.get("_autosaved", "unset") == snapshot:
        return
    try:
        if snapshot is None:
            db.clear_draft()
        else:
            db.save_draft(*snapshot)
        ss["_autosaved"] = snapshot
    except db.DatabaseError:
        pass                                 # autosave is best-effort; manual save still reports errors


# --------------------------------------------------------------------------- callbacks
def cb_new_document() -> None:
    open_in_editor(blank_payload())


def cb_edit_doc(doc_id: int) -> None:
    try:
        doc = db.get_document(doc_id)
    except db.DatabaseError as exc:
        flash("error", f"Could not open the document: {exc}")
        return
    if doc is None:
        flash("error", "That document no longer exists.")
        return
    open_in_editor({"doc_id": doc["id"], "title": doc["title"], "description": doc["description"],
                    "tags": doc["tags"], "content": doc["content"],
                    "created_at": doc["created_at"], "updated_at": doc["updated_at"]})


def cb_view_doc(doc_id: int) -> None:
    ss["view_id"] = doc_id
    goto(PAGE_DOCS)


def cb_use_template(template_id: str) -> None:
    tpl = get_template(template_id)
    if tpl:
        open_in_editor({**blank_payload(), "title": tpl["title"], "content": tpl["content"]})


def cb_confirm_pending() -> None:
    payload, ss["pending_load"] = ss["pending_load"], None
    if payload:
        load_draft(payload)


def cb_cancel_pending() -> None:
    ss["pending_load"] = None


def cb_add_snippet(snippet: str) -> None:
    current = ss.get("w_content", ss["draft"]["content"]).rstrip("\n")
    ss["w_content"] = f"{current}\n\n{snippet}" if current else snippet


def cb_replace_all() -> None:
    find, repl = ss.get("fr_find", ""), ss.get("fr_repl", "")
    if not find:
        flash("warning", "Type the text to find first.")
        return
    text = ss.get("w_content", ss["draft"]["content"])
    count = text.count(find)
    if count == 0:
        flash("info", "No matches found.")
        return
    ss["w_content"] = text.replace(find, repl)
    flash("success", f"Replaced {count} occurrence{'s' if count != 1 else ''}.")


def cb_save() -> None:
    sync_draft()
    d = ss["draft"]
    title = d["title"].strip()
    if not title:
        flash("error", "Please enter a title before saving.")
        return
    tags = db.normalize_tags(d["tags"])
    try:
        message = "Changes saved."
        if d["doc_id"] is not None and db.update_document(
                d["doc_id"], title, d["content"], d["description"], tags):
            doc_id = d["doc_id"]
        else:
            message = ("The original document no longer existed, so it was saved as a new document."
                       if d["doc_id"] is not None else "Document saved.")
            doc_id = db.create_document(title, d["content"], d["description"], tags)
        doc = db.get_document(doc_id)
    except (ValueError, db.DatabaseError) as exc:
        flash("error", f"Could not save: {exc}")
        return
    d.update(doc_id=doc_id, title=title, tags=tags, created_at=doc["created_at"],
             updated_at=doc["updated_at"], saved=(title, d["description"], tags, d["content"]))
    for key, value in (("w_title", title), ("w_tags", tags)):
        if key in ss:
            ss[key] = value
    flash("success", message)


def cb_cancel_edit() -> None:
    sync_draft()
    if is_dirty():
        ss["confirm_cancel"] = True
    else:
        load_draft(blank_payload())
        goto(PAGE_DASH)


def cb_discard_and_home() -> None:
    load_draft(blank_payload())
    goto(PAGE_DASH)


def cb_keep_editing() -> None:
    ss["confirm_cancel"] = False


def cb_restore_version(version_id: int) -> None:
    version = db.get_version(version_id)
    d = ss["draft"]
    if version is None or version["doc_id"] != d["doc_id"]:
        flash("error", "That version is no longer available.")
        return
    d.update(title=version["title"], description=version["description"], content=version["content"])
    for key, _ in EDITOR_WIDGETS:
        ss.pop(key, None)
    flash("info", f"Version from {fmt_dt(version['saved_at'])} loaded into the editor. "
                  "Click “Save document” to keep it.")


def cb_restore_draft() -> None:
    row = ss.get("recover")
    if not row:
        return
    sync_draft()
    if is_dirty():
        flash("warning", "Save or discard what is in the editor before restoring the recovered draft.")
        return
    doc_id, saved = row["doc_id"], None
    created = updated = None
    if doc_id is not None:
        doc = db.get_document(doc_id)
        if doc is None:
            doc_id = None
        else:
            saved = (doc["title"], doc["description"], doc["tags"], doc["content"])
            created, updated = doc["created_at"], doc["updated_at"]
    load_draft({"doc_id": doc_id, "title": row["title"], "description": row["description"],
                "tags": row["tags"], "content": row["content"],
                "created_at": created, "updated_at": updated}, saved)
    ss["recover"] = None
    flash("success", "Your unsaved draft was restored. Click “Save document” to keep it.")
    goto(PAGE_EDIT)


def cb_discard_recovered() -> None:
    ss["recover"] = None
    try:
        db.clear_draft()
    except db.DatabaseError:
        pass


def cb_show_import() -> None:
    ss["show_import"] = True
    goto(PAGE_EDIT)


def cb_import() -> None:
    uploaded = ss.get(f"imp_file_{ss['imp_key']}")
    if uploaded is None:
        flash("warning", "Choose a file to import first.")
        return
    try:
        result = import_file(uploaded.name, uploaded.getvalue())
    except ImportErrorMessage as exc:
        flash("error", str(exc))
        return
    ss["imp_key"] += 1                                  # resets the uploader widget
    open_in_editor({**blank_payload(), "title": result["title"], "content": result["content"]})
    flash("success", f"Imported “{uploaded.name}”. Review it, then click Save document.")


def cb_ask_delete(doc_id: int) -> None:
    ss["confirm_delete"] = doc_id


def cb_cancel_delete() -> None:
    ss["confirm_delete"] = None


def cb_delete(doc_id: int) -> None:
    try:
        deleted = db.delete_document(doc_id)
    except db.DatabaseError as exc:
        flash("error", f"Could not delete the document: {exc}")
        return
    ss["confirm_delete"] = None
    if ss["export_open"] == doc_id:
        ss["export_open"] = None
    if ss["view_id"] == doc_id:
        ss["view_id"] = None
    d = ss["draft"]
    if d["doc_id"] == doc_id:            # editor keeps its text as an unsaved new document
        d["doc_id"], d["saved"] = None, ("", "", "", "")
    flash("success" if deleted else "warning",
          "Document deleted permanently." if deleted else "That document was already deleted.")


def cb_duplicate(doc_id: int) -> None:
    try:
        new_id = db.duplicate_document(doc_id)
    except db.DatabaseError as exc:
        flash("error", f"Could not duplicate the document: {exc}")
        return
    flash("success" if new_id else "error",
          "A copy of the document was created." if new_id else "That document no longer exists.")


def cb_toggle_pin(doc_id: int, pinned: bool) -> None:
    try:
        db.set_pinned(doc_id, not pinned)
    except db.DatabaseError as exc:
        flash("error", f"Could not update the favourite: {exc}")


def cb_toggle_export(doc_id: int) -> None:
    ss["export_open"] = None if ss["export_open"] == doc_id else doc_id


def cb_close_view() -> None:
    ss["view_id"] = None


def cb_update_setting(key: str, widget_key: str, mapping: dict | None = None) -> None:
    value = ss[widget_key]
    if mapping:
        value = mapping[value]
    if isinstance(value, bool):
        value = "1" if value else "0"
    ss["settings"][key] = value
    try:
        db.set_setting(key, value)
    except db.DatabaseError as exc:
        flash("error", f"Setting changed for this session but could not be saved: {exc}")


# --------------------------------------------------------------------------- export
@st.cache_data(show_spinner=False, max_entries=32)
def make_docx(title: str, content: str, description: str, font: str, include_desc: bool,
              page_size: str, page_numbers: bool) -> bytes:
    return build_docx(title, content, description, font, include_desc, page_size, page_numbers)


@st.cache_data(show_spinner=False, max_entries=32)
def make_pdf(title: str, content: str, description: str, include_desc: bool,
             page_size: str, page_numbers: bool) -> bytes:
    return build_pdf(title, content, description, include_desc, page_size, page_numbers)


def export_buttons(title: str, content: str, description: str, prefix: str) -> None:
    """Render Word, PDF, Markdown and text download buttons for the given content."""
    cfg = ss["settings"]
    include = cfg["include_description"] == "1"
    numbers = cfg["page_numbers"] == "1"
    name = (title or "").strip() or "Untitled document"
    try:
        docx_bytes = make_docx(name, content, description, cfg["word_font"], include, cfg["page_size"], numbers)
        pdf_bytes = make_pdf(name, content, description, include, cfg["page_size"], numbers)
        md_text = to_markdown(name, content, description, include)
        txt_text = to_text(name, content, description, include)
    except Exception as exc:  # noqa: BLE001 - show any generation failure to the user
        st.error(f"Could not generate the export file: {exc}")
        return
    default = cfg["default_export"]
    c1, c2, c3, c4 = st.columns(4)
    c1.download_button("⬇️ Word (.docx)", docx_bytes, file_name=safe_filename(name, "docx"),
                       mime=DOCX_MIME, key=f"{prefix}_docx",
                       type="primary" if default == "docx" else "secondary")
    c2.download_button("⬇️ PDF (.pdf)", pdf_bytes, file_name=safe_filename(name, "pdf"),
                       mime="application/pdf", key=f"{prefix}_pdf",
                       type="primary" if default == "pdf" else "secondary")
    c3.download_button("⬇️ Markdown", md_text.encode("utf-8"), file_name=safe_filename(name, "md"),
                       mime="text/markdown", key=f"{prefix}_md")
    c4.download_button("⬇️ Text", txt_text.encode("utf-8"), file_name=safe_filename(name, "txt"),
                       mime="text/plain", key=f"{prefix}_txt")


def render_preview(title: str, description: str, content: str) -> None:
    with st.container(key="preview_paper"):
        st.markdown(f"# {escape_markdown(title.strip() or 'Untitled document')}")
        if description.strip():
            st.markdown(f"*{escape_markdown(description.strip())}*")
        body = preview_markdown(content)
        if body:
            st.markdown(body)
        else:
            st.markdown("*Nothing to preview yet — start writing in the Write tab.*")


def back_home_button(key: str) -> None:
    st.button("← Back to Dashboard", key=key, on_click=goto, args=(PAGE_DASH,))


def recovery_banner() -> None:
    row = ss.get("recover")
    if not row:
        return
    name = escape_markdown(row["title"].strip() or "Untitled")
    st.warning(f"**Unsaved work was recovered** from your last session: “{name}” "
               f"(last autosave {fmt_dt(row['saved_at'])}).")
    a, b, _ = st.columns([1, 1, 2])
    a.button("Restore draft", key="rec_ok", type="primary", on_click=cb_restore_draft)
    b.button("Discard it", key="rec_no", on_click=cb_discard_recovered)


# --------------------------------------------------------------------------- pages
def page_dashboard() -> None:
    ui.hero("Welcome to DocuGen", "Your workspace to create beautiful, professional documents.")
    show_flash()
    recovery_banner()
    try:
        total = db.count_documents()
        recent_count = db.count_recent_documents(7)
        favourites = db.count_pinned()
        recent = db.get_recent_documents(5)
    except db.DatabaseError as exc:
        st.error(f"Could not read your documents: {exc}")
        return

    st.subheader("Quick actions")
    c1, c2, c3, c4 = st.columns(4)
    c1.button("➕ Create a new document", key="qa_new", type="primary", on_click=cb_new_document)
    c2.button("📚 Open saved documents", key="qa_docs", on_click=goto, args=(PAGE_DOCS,))
    c3.button("🧩 Browse templates", key="qa_tpl", on_click=goto, args=(PAGE_TPL,))
    c4.button("📥 Import a file", key="qa_import", on_click=cb_show_import)

    st.write("")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        ui.stat_card("📄", "Saved documents", str(total), "Stored on this computer")
    with s2:
        ui.stat_card("🕒", "Modified this week", str(recent_count), "Changed in the last 7 days")
    with s3:
        ui.stat_card("⭐", "Favorites", str(favourites), "Pinned to the top of My Documents")
    with s4:
        ui.stat_card("🧩", "Templates", str(len(TEMPLATES)), "Ready-made starting points")

    st.write("")
    st.subheader("Recent documents")
    if not recent:
        ui.empty_state("📝", "No documents yet", "Create your first document and it will appear here.")
        st.button("➕ Create your first document", key="empty_new", type="primary", on_click=cb_new_document)
        return
    for doc in recent:
        with st.container(key=f"dgcard_recent_{doc['id']}"):
            info, a, b = st.columns([4, 1, 1])
            with info:
                ui.doc_summary(doc["title"], f"Modified {fmt_dt(doc['updated_at'])}", doc["description"],
                               doc["tags"], bool(doc["pinned"]))
            a.button("👁️ Open", key=f"dash_open_{doc['id']}", on_click=cb_view_doc, args=(doc["id"],))
            b.button("✏️ Edit", key=f"dash_edit_{doc['id']}", on_click=cb_edit_doc, args=(doc["id"],))


def page_editor() -> None:
    d = ss["draft"]
    ui.page_header("✏️", "Document Editor", "Write, preview, save and export your document.")
    show_flash()
    recovery_banner()

    if ss["pending_load"] is not None:
        p = ss["pending_load"]
        target = f"“{p['title']}”" if p.get("doc_id") is not None else (
            f"“{p['title']}”" if p.get("title") else "a new blank document")
        st.warning(f"You have unsaved changes in the editor. Continue to open {target} and discard them?")
        a, b, _ = st.columns([1, 1, 2])
        a.button("Discard and continue", key="pend_ok", type="primary", on_click=cb_confirm_pending)
        b.button("Keep editing", key="pend_no", on_click=cb_cancel_pending)

    if ss["confirm_cancel"]:
        st.warning("You have unsaved changes. Leave the editor and discard them?")
        a, b, _ = st.columns([1, 1, 2])
        a.button("Discard and go Home", key="cancel_ok", type="primary", on_click=cb_discard_and_home)
        b.button("Keep editing", key="cancel_no", on_click=cb_keep_editing)

    for key, field in EDITOR_WIDGETS:
        ss.setdefault(key, d[field])

    if d["doc_id"] is not None:
        st.caption(f"Editing a saved document · Created {fmt_dt(d['created_at'])} · "
                   f"Last modified {fmt_dt(d['updated_at'])}")
    else:
        st.caption("New document — not saved yet.")

    with st.expander("📥 Import a file (.docx, .txt, .md)", expanded=bool(ss.pop("show_import", False))):
        st.file_uploader("Choose a file", type=[e.lstrip(".") for e in SUPPORTED],
                         key=f"imp_file_{ss['imp_key']}", label_visibility="collapsed")
        st.button("Load file into the editor", key="imp_go", on_click=cb_import)
        st.caption("Headings, lists, bold, italic and tables are kept. Nothing is saved until you click Save.")

    st.text_input("Document title", key="w_title", max_chars=db.MAX_TITLE_LEN,
                  placeholder="e.g. Quarterly project report")
    c_desc, c_tags = st.columns([3, 2])
    c_desc.text_input("Description (optional)", key="w_desc", max_chars=db.MAX_DESCRIPTION_LEN,
                      placeholder="A short summary shown under the title")
    c_tags.text_input("Tags (optional, comma-separated)", key="w_tags", max_chars=200,
                      placeholder="work, 2026, draft")

    st.caption("Quick insert — adds formatting to the end of your text:")
    cols = st.columns(len(SNIPPETS))
    for col, (label, snippet) in zip(cols, SNIPPETS.items()):
        col.button(label, key=f"snip_{label}", on_click=cb_add_snippet, args=(snippet,))

    write_tab, preview_tab = st.tabs(["✏️ Write", "👁️ Preview"])
    with write_tab:
        st.text_area("Content", key="w_content", height=420, label_visibility="collapsed",
                     placeholder="Start writing here…")
        sync_draft()
        stats = count_stats(d["content"])
        st.caption(f"{stats['words']:,} words · {stats['characters']:,} characters · "
                   f"{'about ' + str(stats['minutes']) + ' min read' if stats['minutes'] else 'no text yet'}")
        with st.expander("🔎 Find and replace"):
            f1, f2, f3 = st.columns([2, 2, 1])
            f1.text_input("Find", key="fr_find")
            f2.text_input("Replace with", key="fr_repl")
            f3.write("")
            f3.button("Replace all", key="fr_go", on_click=cb_replace_all)
        with st.expander("Formatting guide"):
            st.markdown(
                "- `# Heading`, `## Subheading`, `### Small heading`\n"
                "- `- item` for bullets, `1. item` for numbers; indent by 2 spaces for sub-items\n"
                "- `**bold**`, `*italic*`, `***bold italic***`; write `\\*` for a literal asterisk\n"
                "- Tables: `| Column A | Column B |` lines (first row is the header)\n"
                "- `---` on its own line draws a horizontal rule\n"
                "- A blank line starts a new paragraph; a single line break is kept.\n\n"
                "Tip: click outside the text box (or press Ctrl+Enter) to refresh the preview."
            )
    sync_draft()
    with preview_tab:
        render_preview(d["title"], d["description"], d["content"])

    st.write("")
    s1, s2, s3 = st.columns([1.2, 1, 1])
    s1.button("💾 Save document", key="save_doc", type="primary", on_click=cb_save)
    s2.button("➕ New document", key="new_doc", on_click=cb_new_document)
    s3.button("✖ Cancel / Home", key="cancel_doc", on_click=cb_cancel_edit)

    st.subheader("Export")
    st.caption("Exports use the text currently in the editor, even if it is not saved yet. "
               "Page size and fonts are set in Settings.")
    export_buttons(d["title"], d["content"], d["description"], "ed")

    if d["doc_id"] is not None:
        versions = db.list_versions(d["doc_id"], limit=10)
        with st.expander(f"🕘 Version history ({len(versions)})"):
            if not versions:
                st.caption("Earlier versions appear here each time you save changes to this document.")
            for v in versions:
                row_a, row_b = st.columns([4, 1])
                row_a.caption(f"{fmt_dt(v['saved_at'])} — {escape_markdown(v['title'])} "
                              f"({count_stats(v['content'])['words']:,} words)")
                row_b.button("Restore", key=f"ver_{v['id']}", on_click=cb_restore_version, args=(v["id"],))


def view_panel(doc_id: int) -> None:
    doc = db.get_document(doc_id)
    if doc is None:
        ss["view_id"] = None
        st.warning("That document no longer exists.")
        return
    with st.container(key="dgcard_view"):
        st.subheader("Document preview")
        render_preview(doc["title"], doc["description"], doc["content"])
        st.caption(f"Created {fmt_dt(doc['created_at'])} · Last modified {fmt_dt(doc['updated_at'])}")
        a, b, _ = st.columns([1, 1, 2])
        a.button("✏️ Edit this document", key="view_edit", type="primary", on_click=cb_edit_doc, args=(doc_id,))
        b.button("Close preview", key="view_close", on_click=cb_close_view)
        export_buttons(doc["title"], doc["content"], doc["description"], "view")


def doc_actions(doc: dict) -> None:
    cols = st.columns(6)
    i = doc["id"]
    cols[0].button("👁️ Open", key=f"ml_open_{i}", on_click=cb_view_doc, args=(i,))
    cols[1].button("✏️ Edit", key=f"ml_edit_{i}", on_click=cb_edit_doc, args=(i,))
    cols[2].button("⬇️ Export", key=f"ml_exp_{i}", on_click=cb_toggle_export, args=(i,))
    cols[3].button("📑 Copy", key=f"ml_dup_{i}", on_click=cb_duplicate, args=(i,))
    cols[4].button("★ Unpin" if doc["pinned"] else "☆ Pin", key=f"ml_pin_{i}",
                   on_click=cb_toggle_pin, args=(i, bool(doc["pinned"])))
    cols[5].button("🗑️ Delete", key=f"ml_del_{i}", on_click=cb_ask_delete, args=(i,))


def page_documents() -> None:
    ui.page_header("📚", "My Documents", "Find, open, edit, export and delete your saved documents.")
    show_flash()
    try:
        if ss["view_id"] is not None:
            view_panel(ss["view_id"])
        tags = db.get_all_tags()
        c1, c2, c3 = st.columns([3, 2, 2])
        query = c1.text_input("Search by title", key="doc_search", placeholder="🔍 Search by title…")
        sort_label = c2.selectbox("Sort by", list(SORT_OPTIONS), key="doc_sort")
        tag_label = c3.selectbox("Tag", [ALL_TAGS] + tags, key="doc_tag")
        only_fav = st.checkbox("⭐ Favorites only", key="doc_fav")
        docs = db.get_all_documents(sort=SORT_OPTIONS[sort_label], search=query,
                                    tag="" if tag_label == ALL_TAGS else tag_label,
                                    pinned_only=only_fav, pinned_first=True)
        any_docs = docs or db.count_documents() > 0
    except db.DatabaseError as exc:
        st.error(f"Could not read your documents: {exc}")
        return

    if not docs:
        if any_docs:
            st.info("No documents match your filters. Try a different search, tag or sort.")
        else:
            ui.empty_state("📚", "No saved documents yet", "Documents you save will be listed here.")
            st.button("➕ Create Document", key="docs_empty_new", type="primary", on_click=cb_new_document)
        return

    st.caption(f"{len(docs)} document{'s' if len(docs) != 1 else ''}")
    for doc in docs:
        with st.container(key=f"dgcard_doc_{doc['id']}"):
            ui.doc_summary(doc["title"],
                           f"Modified {fmt_dt(doc['updated_at'])} · Created {fmt_dt(doc['created_at'])}",
                           doc["description"], doc["tags"], bool(doc["pinned"]))
            doc_actions(doc)
            if ss["confirm_delete"] == doc["id"]:
                st.warning("Delete this document permanently? This cannot be undone.")
                x, y, _ = st.columns([1, 1, 2])
                x.button("Yes, delete", key=f"ml_delok_{doc['id']}", type="primary",
                         on_click=cb_delete, args=(doc["id"],))
                y.button("Cancel", key=f"ml_delno_{doc['id']}", on_click=cb_cancel_delete)
            if ss["export_open"] == doc["id"]:
                export_buttons(doc["title"], doc["content"], doc["description"], f"ml_{doc['id']}")


def page_templates() -> None:
    ui.page_header("🧩", "Templates", "Start from a ready-made structure. Nothing is saved until you click Save.")
    show_flash()
    for start in range(0, len(TEMPLATES), 2):
        cols = st.columns(2)
        for col, tpl in zip(cols, TEMPLATES[start:start + 2]):
            with col, st.container(key=f"dgcard_tpl_{tpl['id']}"):
                st.markdown(f"<div class='dg-tpl-icon'>{tpl['icon']}</div>", unsafe_allow_html=True)
                st.markdown(f"**{tpl['name']}**")
                st.caption(tpl["description"])
                st.button("Start blank" if tpl["id"] == "blank" else "Use this template",
                          key=f"tpl_use_{tpl['id']}", type="primary", on_click=cb_use_template, args=(tpl["id"],))
    st.write("")
    back_home_button("tpl_home")


def page_settings() -> None:
    ui.page_header("⚙️", "Settings", "Personalise DocuGen. Changes are saved automatically.")
    show_flash()
    cfg = ss["settings"]
    ss.setdefault("set_theme", "Dark" if cfg["theme"] == "dark" else "Light")
    ss.setdefault("set_export", "PDF (.pdf)" if cfg["default_export"] == "pdf" else "Word (.docx)")
    ss.setdefault("set_font", cfg["word_font"])
    ss.setdefault("set_incdesc", cfg["include_description"] == "1")
    ss.setdefault("set_pagesize", cfg["page_size"])
    ss.setdefault("set_pagenum", cfg["page_numbers"] == "1")

    with st.container(key="dgcard_set_appearance"):
        st.subheader("Appearance")
        st.radio("Theme", list(THEME_MAP), key="set_theme", horizontal=True,
                 on_change=cb_update_setting, args=("theme", "set_theme", THEME_MAP))
    with st.container(key="dgcard_set_export"):
        st.subheader("Export & documents")
        st.radio("Default export format", list(EXPORT_MAP), key="set_export", horizontal=True,
                 on_change=cb_update_setting, args=("default_export", "set_export", EXPORT_MAP),
                 help="The default format is highlighted on download buttons.")
        st.radio("Page size", PAGE_SIZES, key="set_pagesize", horizontal=True,
                 on_change=cb_update_setting, args=("page_size", "set_pagesize"),
                 help="A4 is standard in most countries; Letter in the US and Canada.")
        st.selectbox("Word document font", FONTS, key="set_font",
                     on_change=cb_update_setting, args=("word_font", "set_font"),
                     help="Applies to Word exports. PDFs use Arial (Windows) or the bundled DejaVu Sans.")
        st.checkbox("Show the description under the title in exports", key="set_incdesc",
                    on_change=cb_update_setting, args=("include_description", "set_incdesc"))
        st.checkbox("Add page numbers to Word and PDF exports", key="set_pagenum",
                    on_change=cb_update_setting, args=("page_numbers", "set_pagenum"))
    with st.container(key="dgcard_set_ai"):
        st.subheader("AI assistance")
        st.info("AI-assisted writing is not part of this version. All features — writing, saving, "
                "importing and exporting — work without any AI service or API key.")
    with st.container(key="dgcard_set_about"):
        st.subheader("Application information")
        try:
            count = db.count_documents()
        except db.DatabaseError:
            count = "unavailable"
        st.markdown(f"**DocuGen — AI Document Studio** · version {VERSION}")
        st.caption(f"Database file: {db.get_db_path()}")
        st.caption(f"Saved documents: {count}")
        try:
            backup = db.get_db_path().read_bytes()
            st.download_button("⬇️ Download a backup of my documents (.db)", backup,
                               file_name="docugen-backup.db", mime="application/octet-stream", key="set_backup")
        except OSError:
            st.caption("No database file to back up yet.")


def page_help() -> None:
    ui.page_header("❓", "Help & About", "A quick guide to DocuGen.")
    st.markdown(
        "**Getting started**\n"
        "1. Open **Create Document** (or pick a template, or import a file) and write a title and content.\n"
        "2. Use the **Preview** tab to see how it will look, then click **Save document**.\n"
        "3. Find saved documents in **My Documents** to open, edit, copy, pin, export or delete them.\n"
        "4. Download your work as **Word, PDF, Markdown or plain text** from the Export section.\n\n"
        "**Formatting:** `# Heading`, `- bullets` (indent for sub-items), `1. numbered`, `**bold**`, "
        "`*italic*`, tables with `| a | b |`, and `---` for a rule.\n\n"
        "**Safety nets**\n"
        "- Unsaved text is autosaved; after a refresh or crash DocuGen offers to restore it.\n"
        "- Every time you save changes, the previous text is kept in **Version history** "
        "(last 20 versions per document).\n\n"
        "**Good to know**\n"
        "- DocuGen is a single-user, local application: documents are stored in a SQLite file on this "
        "computer. The file is **not encrypted**, and there is no login.\n"
        "- PDF export needs a font containing your characters; see the README for language limits."
    )
    back_home_button("help_home")


# --------------------------------------------------------------------------- main
def main() -> None:
    init_state()
    if "_goto" in ss:
        ss["nav_page"] = ss.pop("_goto")
    ui.inject_css(ss["settings"]["theme"])

    with st.sidebar:
        ui.sidebar_brand()
        st.radio("Navigation", PAGES, key="nav_page", label_visibility="collapsed",
                 format_func=lambda p: f"{ICONS[p]}  {p}")
        status_slot = st.empty()
        st.caption("Local, single-user app · documents stay on this computer.")

    page = ss["nav_page"]
    if page == PAGE_DASH:
        page_dashboard()
    elif page == PAGE_EDIT:
        page_editor()
    elif page == PAGE_DOCS:
        page_documents()
    elif page == PAGE_TPL:
        page_templates()
    elif page == PAGE_SET:
        page_settings()
    elif page == PAGE_HELP:
        page_help()
    else:
        st.error("Unknown page.")

    autosave()
    with status_slot.container():
        if is_dirty():
            ui.badge("● Unsaved changes in editor (autosaved)", warn=True)
        elif ss["draft"]["doc_id"] is not None:
            ui.badge("✓ Editor is saved")


main()
