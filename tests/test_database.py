import os
import sqlite3
import time

import pytest

import database as db


@pytest.fixture()
def path(tmp_path):
    p = tmp_path / "sub" / "test.db"      # parent directory does not exist yet
    db.init_db(p)
    return p


def test_init_creates_file_and_tables(path):
    assert path.exists()
    with sqlite3.connect(path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"documents", "settings"} <= tables


def test_init_is_idempotent(path):
    db.create_document("A", "x", db_path=path)
    db.init_db(path)
    assert db.count_documents(path) == 1


def test_create_and_get(path):
    doc_id = db.create_document("  My Title  ", "Body", "Desc", db_path=path)
    doc = db.get_document(doc_id, path)
    assert doc["title"] == "My Title" and doc["content"] == "Body" and doc["description"] == "Desc"
    assert doc["created_at"] == doc["updated_at"]


def test_get_missing_returns_none(path):
    assert db.get_document(999, path) is None


def test_update_changes_fields_and_timestamp(path):
    doc_id = db.create_document("Old", "old", db_path=path)
    before = db.get_document(doc_id, path)
    time.sleep(0.01)
    assert db.update_document(doc_id, "New", "new", "d", db_path=path) is True
    after = db.get_document(doc_id, path)
    assert (after["title"], after["content"], after["description"]) == ("New", "new", "d")
    assert after["updated_at"] > before["updated_at"]
    assert after["created_at"] == before["created_at"]


def test_update_missing_returns_false(path):
    assert db.update_document(123, "T", "c", db_path=path) is False


def test_delete(path):
    doc_id = db.create_document("Gone", db_path=path)
    assert db.delete_document(doc_id, path) is True
    assert db.get_document(doc_id, path) is None
    assert db.delete_document(doc_id, path) is False


def test_validation(path):
    with pytest.raises(ValueError):
        db.create_document("   ", "x", db_path=path)
    with pytest.raises(ValueError):
        db.create_document("x" * (db.MAX_TITLE_LEN + 1), db_path=path)
    with pytest.raises(ValueError):
        db.update_document(1, "", db_path=path)


def test_search_and_special_characters(path):
    db.create_document("Annual Report", db_path=path)
    db.create_document("Meeting notes", db_path=path)
    db.create_document("100% done_ok", db_path=path)
    assert [d["title"] for d in db.search_documents("report", db_path=path)] == ["Annual Report"]
    assert len(db.search_documents("", db_path=path)) == 3
    assert [d["title"] for d in db.search_documents("100%", db_path=path)] == ["100% done_ok"]
    assert db.search_documents("%", db_path=path)[0]["title"] == "100% done_ok"   # % is literal
    assert len(db.search_documents("_", db_path=path)) == 1                        # _ is literal
    assert db.search_documents("'; DROP TABLE documents; --", db_path=path) == []
    assert db.count_documents(path) == 3


def test_sorting(path):
    a = db.create_document("banana", db_path=path)
    time.sleep(0.01)
    b = db.create_document("Apple", db_path=path)
    time.sleep(0.01)
    c = db.create_document("cherry", db_path=path)
    ids = lambda s: [d["id"] for d in db.get_all_documents(sort=s, db_path=path)]
    assert ids("newest") == [c, b, a]
    assert ids("oldest") == [a, b, c]
    assert ids("az") == [b, a, c]
    time.sleep(0.01)
    db.update_document(a, "banana", "edited", db_path=path)
    assert ids("recent")[0] == a
    assert ids("bogus-value") == ids("recent")            # unknown sort falls back safely


def test_recent_and_counts(path):
    for i in range(7):
        db.create_document(f"Doc {i}", db_path=path)
    recent = db.get_recent_documents(5, path)
    assert len(recent) == 5 and recent[0]["title"] == "Doc 6"
    assert db.count_documents(path) == 7
    assert db.count_recent_documents(7, path) == 7
    assert db.count_recent_documents(0, path) == 0


def test_persistence_across_connections(path):
    doc_id = db.create_document("Persist", "data \u2713 unicode", db_path=path)
    # a brand-new module-level call (new connection) must see the data
    assert db.get_document(doc_id, path)["content"] == "data \u2713 unicode"


def test_settings_roundtrip(path):
    assert db.get_setting("theme", "light", path) == "light"
    db.set_setting("theme", "dark", path)
    db.set_setting("theme", "dark", path)
    assert db.get_setting("theme", db_path=path) == "dark"
    assert db.get_all_settings(path) == {"theme": "dark"}


def test_env_var_path_and_missing_file_recreated(tmp_path, monkeypatch):
    target = tmp_path / "env.db"
    monkeypatch.setenv("DOCUGEN_DB_PATH", str(target))
    assert db.get_db_path() == target
    db.init_db()
    assert target.exists()
    target.unlink()                                       # "missing database file"
    db.init_db()
    assert db.count_documents() == 0


def test_unwritable_location_raises_database_error(tmp_path):
    blocker = tmp_path / "file.txt"
    blocker.write_text("x")
    with pytest.raises(db.DatabaseError):
        db.init_db(blocker / "child.db")
