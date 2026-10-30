"""App-level tests for DocuGen 2 features."""
import pathlib

import pytest
from streamlit.testing.v1 import AppTest

import database as db

APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUGEN_DB_PATH", str(tmp_path / "v2app.db"))
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


def new_session():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def test_autosave_and_recovery_after_restart(app):
    go(app, "Create Document")
    app.text_input(key="w_title").set_value("Precious draft").run()
    app.text_area(key="w_content").set_value("Do not lose me").run()
    assert db.get_draft()["content"] == "Do not lose me"
    restarted = new_session()                                  # simulates refresh / crash recovery
    assert restarted.session_state["recover"]["title"] == "Precious draft"
    assert any("recovered" in w.value.lower() for w in restarted.warning)
    assert db.get_draft() is not None                          # not wiped by the new session
    button(restarted, "rec_ok").click().run()
    assert not restarted.exception
    assert restarted.text_input(key="w_title").value == "Precious draft"
    assert restarted.text_area(key="w_content").value == "Do not lose me"
    assert restarted.session_state["recover"] is None


def test_discarding_recovered_draft_clears_it(app):
    go(app, "Create Document")
    app.text_input(key="w_title").set_value("Throwaway").run()
    restarted = new_session()
    button(restarted, "rec_no").click().run()
    assert db.get_draft() is None and restarted.session_state["recover"] is None
    assert new_session().session_state["recover"] is None


def test_saving_clears_autosaved_draft(app):
    go(app, "Create Document")
    app.text_input(key="w_title").set_value("Saved one").run()
    assert db.get_draft() is not None
    button(app, "save_doc").click().run()
    assert db.get_draft() is None


def test_tags_saved_normalized_and_filterable(app):
    go(app, "Create Document")
    app.text_input(key="w_title").set_value("Tagged").run()
    app.text_input(key="w_tags").set_value(" Work, URGENT ,work").run()
    button(app, "save_doc").click().run()
    assert db.get_document(app.session_state["draft"]["doc_id"])["tags"] == "work,urgent"
    assert app.text_input(key="w_tags").value == "work,urgent"
    db.create_document("Other", "x", tags="home")
    go(app, "My Documents")
    app.selectbox(key="doc_tag").set_value("work").run()
    assert [b.key for b in app.button if b.key.startswith("ml_del_")] == [
        f"ml_del_{app.session_state['draft']['doc_id']}"]
    assert any("work" in m.value and "dg-chip" in m.value for m in app.markdown)


def test_pin_duplicate_and_favorites_filter(app):
    a = db.create_document("Alpha", "a")
    b = db.create_document("Beta", "b")
    go(app, "My Documents")
    button(app, f"ml_pin_{a}").click().run()
    assert db.get_document(a)["pinned"] == 1
    assert [x.key for x in app.button if x.key.startswith("ml_del_")][0] == f"ml_del_{a}"   # pinned first
    app.checkbox(key="doc_fav").set_value(True).run()
    assert [x.key for x in app.button if x.key.startswith("ml_del_")] == [f"ml_del_{a}"]
    app.checkbox(key="doc_fav").set_value(False).run()
    button(app, f"ml_dup_{b}").click().run()
    assert db.count_documents() == 3
    assert any(d["title"] == "Beta (copy)" for d in db.get_all_documents())
    assert any("copy" in s.value.lower() for s in app.success)


def test_version_history_restore_flow(app):
    go(app, "Create Document")
    app.text_input(key="w_title").set_value("Versioned").run()
    app.text_area(key="w_content").set_value("first draft").run()
    button(app, "save_doc").click().run()
    app.text_area(key="w_content").set_value("second draft").run()
    button(app, "save_doc").click().run()
    doc_id = app.session_state["draft"]["doc_id"]
    versions = db.list_versions(doc_id)
    assert [v["content"] for v in versions] == ["first draft"]
    button(app, f"ver_{versions[0]['id']}").click().run()
    assert app.text_area(key="w_content").value == "first draft"
    assert db.get_document(doc_id)["content"] == "second draft"        # nothing changed until Save
    button(app, "save_doc").click().run()
    assert db.get_document(doc_id)["content"] == "first draft"
    assert len(db.list_versions(doc_id)) == 2


def test_find_and_replace(app):
    go(app, "Create Document")
    app.text_area(key="w_content").set_value("cat dog cat").run()
    app.text_input(key="fr_find").set_value("cat").run()
    app.text_input(key="fr_repl").set_value("bird").run()
    button(app, "fr_go").click().run()
    assert app.text_area(key="w_content").value == "bird dog bird"
    assert any("2 occurrences" in s.value for s in app.success)


def test_quick_insert_table_and_word_count(app):
    go(app, "Create Document")
    app.text_area(key="w_content").set_value("one two three").run()
    assert any("3 words" in c.value for c in app.caption)
    button(app, "snip_Table").click().run()
    assert "| Column A | Column B |" in app.text_area(key="w_content").value


def test_new_settings_persist_and_flow_into_exports(app):
    go(app, "Settings")
    app.radio(key="set_pagesize").set_value("Letter").run()
    app.checkbox(key="set_pagenum").set_value(False).run()
    assert db.get_setting("page_size") == "Letter" and db.get_setting("page_numbers") == "0"
    fresh = new_session()
    assert fresh.session_state["settings"]["page_size"] == "Letter"
    go(app, "Create Document")
    app.text_input(key="w_title").set_value("Export me").run()
    assert not app.exception                       # export panel renders with the new settings


def test_dashboard_shows_favorites_and_import_shortcut(app):
    a = db.create_document("Fav", "x")
    db.set_pinned(a, True)
    go(app, "Dashboard")
    html = " ".join(m.value for m in app.markdown)
    assert "Favorites" in html and ">1<" in html
    button(app, "qa_import").click().run()
    assert app.session_state["nav_page"] == "Create Document" and not app.exception


def test_all_templates_load_and_export(app):
    from services.templates import TEMPLATES
    from services.word_export import build_docx
    from services.pdf_export import build_pdf
    for t in TEMPLATES:
        assert build_docx(t["title"], t["content"]) and build_pdf(t["title"], t["content"])
    assert any("| Milestone |" in t["content"] for t in TEMPLATES)
