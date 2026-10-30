import sqlite3
import time

import pytest

import database as db


@pytest.fixture()
def path(tmp_path):
    p = tmp_path / "v2.db"
    db.init_db(p)
    return p


def test_upgrade_from_v1_database_keeps_data(tmp_path):
    old = tmp_path / "old.db"
    with sqlite3.connect(old) as conn:        # exact DocuGen 1.x schema
        conn.execute("""CREATE TABLE documents (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', content TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        conn.execute("INSERT INTO documents (title, content, created_at, updated_at) VALUES ('Old doc','text','2025-01-01','2025-01-02')")
    db.init_db(old)
    doc = db.get_document(1, old)
    assert doc["title"] == "Old doc" and doc["pinned"] == 0 and doc["tags"] == ""
    assert db.update_document(1, "Old doc", "new text", tags="a, b", db_path=old)
    assert db.list_versions(1, db_path=old)[0]["content"] == "text"
    db.init_db(old)                           # running again is harmless
    assert db.count_documents(old) == 1


def test_normalize_tags():
    assert db.normalize_tags(" Work, work ,  2026 ,, Big   Idea ") == "work,2026,big idea"
    assert db.normalize_tags(None) == ""
    assert len(db.normalize_tags(",".join(f"t{i}" for i in range(30))).split(",")) == db.MAX_TAGS
    assert len(db.normalize_tags("x" * 100)) == db.MAX_TAG_LEN


def test_tags_filter_and_listing(path):
    db.create_document("A", tags="work, urgent", db_path=path)
    db.create_document("B", tags="personal", db_path=path)
    db.create_document("C", tags="networking", db_path=path)
    assert db.get_all_tags(path) == ["networking", "personal", "urgent", "work"]
    assert [d["title"] for d in db.get_all_documents(tag="work", db_path=path)] == ["A"]
    assert [d["title"] for d in db.get_all_documents(tag="WORK", db_path=path)] == ["A"]   # case-insensitive
    assert db.get_all_documents(tag="net", db_path=path) == []                              # whole tags only
    assert db.get_all_documents(tag="%", db_path=path) == []


def test_pinning_and_pinned_first(path):
    a = db.create_document("A", db_path=path)
    time.sleep(0.01)
    b = db.create_document("B", db_path=path)
    before = db.get_document(a, path)["updated_at"]
    assert db.set_pinned(a, True, path) and db.count_pinned(path) == 1
    assert db.get_document(a, path)["updated_at"] == before          # pinning is not an edit
    assert [d["id"] for d in db.get_all_documents(pinned_first=True, db_path=path)] == [a, b]
    assert [d["id"] for d in db.get_all_documents(pinned_only=True, db_path=path)] == [a]
    assert db.set_pinned(999, True, path) is False
    db.set_pinned(a, False, path)
    assert db.count_pinned(path) == 0


def test_duplicate(path):
    a = db.create_document("Original", "body", "desc", "x,y", db_path=path)
    b = db.duplicate_document(a, path)
    copy = db.get_document(b, path)
    assert copy["title"] == "Original (copy)" and copy["content"] == "body" and copy["tags"] == "x,y"
    long_id = db.create_document("T" * db.MAX_TITLE_LEN, db_path=path)
    assert len(db.get_document(db.duplicate_document(long_id, path), path)["title"]) <= db.MAX_TITLE_LEN
    assert db.duplicate_document(999, path) is None


def test_versions_created_only_on_real_changes_and_trimmed(path):
    doc = db.create_document("V", "v0", db_path=path)
    db.update_document(doc, "V", "v0", db_path=path)                 # no change -> no version
    assert db.list_versions(doc, db_path=path) == []
    for i in range(1, db.MAX_VERSIONS + 6):
        db.update_document(doc, "V", f"v{i}", db_path=path)
    versions = db.list_versions(doc, limit=100, db_path=path)
    assert len(versions) == db.MAX_VERSIONS
    assert versions[0]["content"] == f"v{db.MAX_VERSIONS + 4}"       # newest snapshot first
    assert db.get_version(versions[0]["id"], path)["doc_id"] == doc


def test_update_without_tags_keeps_tags(path):
    doc = db.create_document("T", tags="keep", db_path=path)
    db.update_document(doc, "T2", "c", db_path=path)
    assert db.get_document(doc, path)["tags"] == "keep"
    db.update_document(doc, "T2", "c", tags="", db_path=path)
    assert db.get_document(doc, path)["tags"] == ""


def test_deleting_document_removes_versions(path):
    doc = db.create_document("D", "a", db_path=path)
    db.update_document(doc, "D", "b", db_path=path)
    db.delete_document(doc, path)
    assert db.list_versions(doc, db_path=path) == []


def test_draft_roundtrip(path):
    assert db.get_draft(path) is None
    db.save_draft(None, "T", "d", "tag", "body", path)
    db.save_draft(5, "T2", "", "", "body2", path)                   # single row, overwritten
    draft = db.get_draft(path)
    assert (draft["doc_id"], draft["title"], draft["content"]) == (5, "T2", "body2")
    db.clear_draft(path)
    assert db.get_draft(path) is None
