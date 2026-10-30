"""Application-level tests using Streamlit's headless AppTest runner."""
import ast
import importlib
import pathlib

import pytest
from streamlit.testing.v1 import AppTest

import database as db

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")


def test_all_python_files_have_valid_syntax_and_no_code_fences():
    files = [p for p in ROOT.rglob("*.py") if ".venv" not in p.parts]
    assert files
    for path in files:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
        assert ("`" * 3) not in source, f"Markdown fence found in {path}"


@pytest.mark.parametrize("module", ["database", "services.formatting", "services.word_export",
                                    "services.pdf_export", "services.templates", "services.utils",
                                    "components.ui"])
def test_imports(module):
    importlib.import_module(module)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUGEN_DB_PATH", str(tmp_path / "app.db"))
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def go(at, page):
    at.session_state["nav_page"] = page
    at.run()
    assert not at.exception, at.exception


def button(at, key):
    return next(b for b in at.button if b.key == key)


def test_startup_dashboard_empty_state(app):
    text = " ".join(m.value for m in app.markdown)
    assert "Welcome to DocuGen" in text
    assert "Your workspace to create beautiful, professional documents." in text
    assert "No documents yet" in text
    options = [o.split("  ", 1)[1] for o in app.sidebar.radio[0].options]
    assert options == ["Dashboard", "Create Document", "My Documents", "Templates", "Settings", "Help & About"]


def test_every_page_renders(app):
    for page in ["Create Document", "My Documents", "Templates", "Settings", "Help & About", "Dashboard"]:
        go(app, page)


def test_template_to_editor_and_save_flow(app, tmp_path):
    go(app, "Templates")
    assert len([b for b in app.button if b.key.startswith("tpl_use_")]) == 8
    button(app, "tpl_use_meeting_minutes").click().run()
    assert not app.exception
    assert app.session_state["nav_page"] == "Create Document"
    assert app.text_input(key="w_title").value == "Meeting Minutes"
    assert "## Attendees" in app.text_area(key="w_content").value
    assert db.count_documents() == 0                       # selecting a template saves nothing
    button(app, "save_doc").click().run()
    assert db.count_documents() == 1
    assert app.session_state["draft"]["doc_id"] is not None


def test_save_requires_title(app):
    go(app, "Create Document")
    button(app, "save_doc").click().run()
    assert db.count_documents() == 0
    assert any("title" in e.value.lower() for e in app.error)


def test_create_edit_update_does_not_duplicate_or_overwrite_others(app):
    go(app, "Create Document")
    app.text_input(key="w_title").set_value("First").run()
    app.text_area(key="w_content").set_value("# Hello\n\nBody").run()
    button(app, "save_doc").click().run()
    first_id = app.session_state["draft"]["doc_id"]
    app.text_area(key="w_content").set_value("Changed body").run()
    button(app, "save_doc").click().run()
    assert db.count_documents() == 1
    assert db.get_document(first_id)["content"] == "Changed body"
    # new document must not overwrite the first one
    button(app, "new_doc").click().run()
    assert app.session_state["draft"]["doc_id"] is None
    assert app.text_input(key="w_title").value == ""
    app.text_input(key="w_title").set_value("Second").run()
    button(app, "save_doc").click().run()
    assert db.count_documents() == 2
    assert db.get_document(first_id)["title"] == "First"


def test_unsaved_changes_prompt_before_discarding(app):
    go(app, "Create Document")
    app.text_input(key="w_title").set_value("Draft in progress").run()
    go(app, "Templates")
    button(app, "tpl_use_resume").click().run()
    assert app.session_state["pending_load"] is not None
    assert app.session_state["draft"]["title"] == "Draft in progress"   # not discarded yet
    button(app, "pend_no").click().run()
    assert app.text_input(key="w_title").value == "Draft in progress"
    go(app, "Templates")
    button(app, "tpl_use_resume").click().run()
    button(app, "pend_ok").click().run()
    assert app.text_input(key="w_title").value == "Resume"


def test_editor_content_survives_navigation(app):
    go(app, "Create Document")
    app.text_input(key="w_title").set_value("Keep me").run()
    app.text_area(key="w_content").set_value("Important unsaved text").run()
    go(app, "Settings")
    go(app, "Create Document")
    assert app.text_input(key="w_title").value == "Keep me"
    assert app.text_area(key="w_content").value == "Important unsaved text"


def test_my_documents_search_sort_delete_with_confirmation(app):
    a = db.create_document("Alpha plan", "a")
    b = db.create_document("Beta report", "b")
    go(app, "My Documents")
    assert len([b_ for b_ in app.button if b_.key.startswith("ml_del_")]) == 2
    app.text_input(key="doc_search").set_value("beta").run()
    assert [b_.key for b_ in app.button if b_.key.startswith("ml_del_")] == [f"ml_del_{b}"]
    app.text_input(key="doc_search").set_value("").run()
    button(app, f"ml_del_{a}").click().run()
    assert db.count_documents() == 2                       # nothing deleted before confirmation
    button(app, f"ml_delok_{a}").click().run()
    assert db.count_documents() == 1 and db.get_document(a) is None
    assert any("deleted" in s.value.lower() for s in app.success)


def test_delete_can_be_cancelled(app):
    a = db.create_document("Keep", "x")
    go(app, "My Documents")
    button(app, f"ml_del_{a}").click().run()
    button(app, f"ml_delno_{a}").click().run()
    assert db.get_document(a) is not None


def test_open_and_edit_existing_document(app):
    a = db.create_document("Stored", "# Stored heading", "desc")
    go(app, "My Documents")
    button(app, f"ml_open_{a}").click().run()
    assert app.session_state["view_id"] == a
    button(app, "view_edit").click().run()
    assert app.session_state["nav_page"] == "Create Document"
    assert app.text_input(key="w_title").value == "Stored"
    assert app.text_area(key="w_content").value == "# Stored heading"


def test_export_panel_shows_downloads(app):
    a = db.create_document("Exportable", "text")
    go(app, "My Documents")
    button(app, f"ml_exp_{a}").click().run()
    assert not app.exception


def test_dashboard_statistics_reflect_database(app):
    db.create_document("One", "x")
    db.create_document("Two", "y")
    go(app, "Dashboard")
    html = " ".join(m.value for m in app.markdown)
    assert ">2<" in html                                    # total saved documents
    assert "One" in html and "Two" in html                  # recent documents


def test_theme_switching_changes_css_and_persists(app):
    def css():
        return " ".join(m.value for m in app.markdown if "<style>" in m.value)
    assert "--dg-bg:linear-gradient(160deg,#eef2ff" in css()
    go(app, "Settings")
    app.radio(key="set_theme").set_value("Dark").run()
    assert "--dg-bg:linear-gradient(160deg,#0b0c1f" in css()
    assert db.get_setting("theme") == "dark"
    # a brand-new session (restart) loads the stored preference
    fresh = AppTest.from_file(APP, default_timeout=60)
    fresh.run()
    assert "#0b0c1f" in " ".join(m.value for m in fresh.markdown if "<style>" in m.value)


def test_default_export_setting_persists(app):
    go(app, "Settings")
    app.radio(key="set_export").set_value("PDF (.pdf)").run()
    assert db.get_setting("default_export") == "pdf"


def test_document_text_is_never_rendered_as_html(app):
    db.create_document("<img src=x onerror=alert(1)>", "<script>alert(1)</script>")
    go(app, "My Documents")
    joined = " ".join(m.value for m in app.markdown)
    assert "<img src=x" not in joined
    assert "&lt;img src=x" in joined


def test_cancel_with_unsaved_changes_asks_for_confirmation(app):
    go(app, "Create Document")
    app.text_input(key="w_title").set_value("Something").run()
    button(app, "cancel_doc").click().run()
    assert app.session_state["confirm_cancel"] is True
    assert app.session_state["nav_page"] == "Create Document"
    button(app, "cancel_ok").click().run()
    assert app.session_state["nav_page"] == "Dashboard"
    assert app.session_state["draft"]["title"] == ""


def test_persistence_across_app_restart(app):
    go(app, "Create Document")
    app.text_input(key="w_title").set_value("Survivor").run()
    button(app, "save_doc").click().run()
    restarted = AppTest.from_file(APP, default_timeout=60)
    restarted.run()
    assert not restarted.exception
    assert "Survivor" in " ".join(m.value for m in restarted.markdown)
