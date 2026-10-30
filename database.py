"""SQLite persistence layer for DocuGen 2.

All SQL lives in this module. Every query is parameterised. The database file
and its parent directory are created automatically, and databases created by
DocuGen 1.x are upgraded in place (no data is lost).
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
MAX_TITLE_LEN = 200
MAX_DESCRIPTION_LEN = 500
MAX_CONTENT_LEN = 1_000_000
MAX_TAGS = 10
MAX_TAG_LEN = 30
MAX_VERSIONS = 20

SORT_ORDERS = {
    "recent": "updated_at DESC, id DESC",
    "newest": "created_at DESC, id DESC",
    "oldest": "created_at ASC, id ASC",
    "az": "title COLLATE NOCASE ASC, id ASC",
}


class DatabaseError(Exception):
    """Raised when the database cannot be read or written."""


def get_db_path() -> Path:
    """Resolve the database path (env var DOCUGEN_DB_PATH or data/docugen.db)."""
    configured = os.environ.get("DOCUGEN_DB_PATH", "").strip()
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_absolute() else PROJECT_ROOT / path
    return PROJECT_ROOT / "data" / "docugen.db"


def _now() -> str:
    return datetime.now().isoformat(timespec="microseconds")


@contextmanager
def _connect(db_path: Optional[os.PathLike] = None) -> Iterator[sqlite3.Connection]:
    path = Path(db_path) if db_path else get_db_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), timeout=10)
    except (OSError, sqlite3.Error) as exc:
        raise DatabaseError(f"Cannot open the database at '{path}': {exc}") from exc
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise DatabaseError(f"Database error: {exc}") from exc
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[os.PathLike] = None) -> None:
    """Create the database and tables, and upgrade older databases."""
    with _connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS documents (
                   id          INTEGER PRIMARY KEY AUTOINCREMENT,
                   title       TEXT NOT NULL,
                   description TEXT NOT NULL DEFAULT '',
                   content     TEXT NOT NULL DEFAULT '',
                   created_at  TEXT NOT NULL,
                   updated_at  TEXT NOT NULL,
                   pinned      INTEGER NOT NULL DEFAULT 0,
                   tags        TEXT NOT NULL DEFAULT ''
               )"""
        )
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(documents)")}
        if "pinned" not in existing:                      # upgrade from DocuGen 1.x
            conn.execute("ALTER TABLE documents ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
        if "tags" not in existing:
            conn.execute("ALTER TABLE documents ADD COLUMN tags TEXT NOT NULL DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_updated ON documents(updated_at)")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS versions (
                   id          INTEGER PRIMARY KEY AUTOINCREMENT,
                   doc_id      INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                   title       TEXT NOT NULL,
                   description TEXT NOT NULL DEFAULT '',
                   content     TEXT NOT NULL DEFAULT '',
                   saved_at    TEXT NOT NULL
               )"""
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_versions_doc ON versions(doc_id)")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS draft (
                   id          INTEGER PRIMARY KEY CHECK (id = 1),
                   doc_id      INTEGER,
                   title       TEXT NOT NULL DEFAULT '',
                   description TEXT NOT NULL DEFAULT '',
                   tags        TEXT NOT NULL DEFAULT '',
                   content     TEXT NOT NULL DEFAULT '',
                   saved_at    TEXT NOT NULL
               )"""
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )


# ------------------------------------------------------------------ validation
def normalize_tags(tags: Optional[str]) -> str:
    """Normalise a comma-separated tag string: trimmed, lower-case, unique, limited."""
    seen: list[str] = []
    for raw in (tags or "").split(","):
        tag = " ".join(raw.split())[:MAX_TAG_LEN].lower()
        if tag and tag not in seen:
            seen.append(tag)
    return ",".join(seen[:MAX_TAGS])


def _validate(title: str, content: str, description: str) -> tuple[str, str, str]:
    title = (title or "").strip()
    description = (description or "").strip()
    content = content or ""
    if not title:
        raise ValueError("The title cannot be empty.")
    if len(title) > MAX_TITLE_LEN:
        raise ValueError(f"The title is too long (maximum {MAX_TITLE_LEN} characters).")
    if len(description) > MAX_DESCRIPTION_LEN:
        raise ValueError(f"The description is too long (maximum {MAX_DESCRIPTION_LEN} characters).")
    if len(content) > MAX_CONTENT_LEN:
        raise ValueError(f"The content is too long (maximum {MAX_CONTENT_LEN:,} characters).")
    return title, content, description


def _row(row: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(row) if row is not None else None


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ------------------------------------------------------------------ documents
def create_document(title: str, content: str = "", description: str = "", tags: str = "",
                    db_path: Optional[os.PathLike] = None) -> int:
    title, content, description = _validate(title, content, description)
    now = _now()
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO documents (title, description, content, created_at, updated_at, tags) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, description, content, now, now, normalize_tags(tags)),
        )
        return int(cur.lastrowid)


def get_document(doc_id: int, db_path: Optional[os.PathLike] = None) -> Optional[dict]:
    with _connect(db_path) as conn:
        return _row(conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone())


def get_all_documents(sort: str = "recent", search: str = "", tag: str = "",
                      pinned_only: bool = False, pinned_first: bool = False,
                      db_path: Optional[os.PathLike] = None) -> list[dict]:
    order = SORT_ORDERS.get(sort, SORT_ORDERS["recent"])  # whitelist -> safe to interpolate
    if pinned_first:
        order = "pinned DESC, " + order
    clauses: list[str] = []
    params: list = []
    search = (search or "").strip()
    if search:
        clauses.append("title LIKE ? ESCAPE '\\'")
        params.append(f"%{_escape_like(search)}%")
    tag = normalize_tags(tag)
    if tag:
        clauses.append("(',' || tags || ',') LIKE ? ESCAPE '\\'")
        params.append(f"%,{_escape_like(tag)},%")
    if pinned_only:
        clauses.append("pinned = 1")
    sql = "SELECT * FROM documents"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += f" ORDER BY {order}"
    with _connect(db_path) as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def search_documents(query: str, sort: str = "recent",
                     db_path: Optional[os.PathLike] = None) -> list[dict]:
    return get_all_documents(sort=sort, search=query, db_path=db_path)


def update_document(doc_id: int, title: str, content: str = "", description: str = "",
                    tags: Optional[str] = None, db_path: Optional[os.PathLike] = None) -> bool:
    """Update a document, keeping the previous text as a version.

    Returns False if no document with that id exists. `tags=None` leaves tags unchanged.
    """
    title, content, description = _validate(title, content, description)
    with _connect(db_path) as conn:
        old = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if old is None:
            return False
        if (old["title"], old["description"], old["content"]) != (title, description, content):
            conn.execute(
                "INSERT INTO versions (doc_id, title, description, content, saved_at) VALUES (?, ?, ?, ?, ?)",
                (doc_id, old["title"], old["description"], old["content"], old["updated_at"]),
            )
            conn.execute(
                "DELETE FROM versions WHERE doc_id = ? AND id NOT IN "
                "(SELECT id FROM versions WHERE doc_id = ? ORDER BY id DESC LIMIT ?)",
                (doc_id, doc_id, MAX_VERSIONS),
            )
        new_tags = old["tags"] if tags is None else normalize_tags(tags)
        conn.execute(
            "UPDATE documents SET title = ?, description = ?, content = ?, tags = ?, updated_at = ? "
            "WHERE id = ?",
            (title, description, content, new_tags, _now(), doc_id),
        )
        return True


def delete_document(doc_id: int, db_path: Optional[os.PathLike] = None) -> bool:
    with _connect(db_path) as conn:
        return conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,)).rowcount > 0


def duplicate_document(doc_id: int, db_path: Optional[os.PathLike] = None) -> Optional[int]:
    """Create a copy titled '<title> (copy)'. Returns the new id, or None if missing."""
    with _connect(db_path) as conn:
        src = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if src is None:
            return None
        suffix = " (copy)"
        title = src["title"][: MAX_TITLE_LEN - len(suffix)] + suffix
        now = _now()
        cur = conn.execute(
            "INSERT INTO documents (title, description, content, created_at, updated_at, tags) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, src["description"], src["content"], now, now, src["tags"]),
        )
        return int(cur.lastrowid)


def set_pinned(doc_id: int, pinned: bool, db_path: Optional[os.PathLike] = None) -> bool:
    """Mark/unmark a document as favourite without changing its modified time."""
    with _connect(db_path) as conn:
        return conn.execute(
            "UPDATE documents SET pinned = ? WHERE id = ?", (1 if pinned else 0, doc_id)
        ).rowcount > 0


def get_recent_documents(limit: int = 5, db_path: Optional[os.PathLike] = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM documents ORDER BY {SORT_ORDERS['recent']} LIMIT ?", (int(limit),)
        ).fetchall()
        return [dict(r) for r in rows]


def count_documents(db_path: Optional[os.PathLike] = None) -> int:
    with _connect(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])


def count_pinned(db_path: Optional[os.PathLike] = None) -> int:
    with _connect(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM documents WHERE pinned = 1").fetchone()[0])


def count_recent_documents(days: int = 7, db_path: Optional[os.PathLike] = None) -> int:
    """Number of documents modified within the last `days` days."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="microseconds")
    with _connect(db_path) as conn:
        return int(conn.execute(
            "SELECT COUNT(*) FROM documents WHERE updated_at >= ?", (cutoff,)
        ).fetchone()[0])


def get_all_tags(db_path: Optional[os.PathLike] = None) -> list[str]:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT tags FROM documents WHERE tags != ''").fetchall()
    return sorted({t for r in rows for t in r["tags"].split(",") if t})


# ------------------------------------------------------------------ versions
def list_versions(doc_id: int, limit: int = MAX_VERSIONS,
                  db_path: Optional[os.PathLike] = None) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM versions WHERE doc_id = ? ORDER BY id DESC LIMIT ?", (doc_id, int(limit))
        ).fetchall()
        return [dict(r) for r in rows]


def get_version(version_id: int, db_path: Optional[os.PathLike] = None) -> Optional[dict]:
    with _connect(db_path) as conn:
        return _row(conn.execute("SELECT * FROM versions WHERE id = ?", (version_id,)).fetchone())


# ------------------------------------------------------------------ draft recovery
def save_draft(doc_id: Optional[int], title: str, description: str, tags: str, content: str,
               db_path: Optional[os.PathLike] = None) -> None:
    """Store the single unsaved editor draft so it survives a refresh or crash."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO draft (id, doc_id, title, description, tags, content, saved_at) "
            "VALUES (1, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET doc_id = excluded.doc_id, title = excluded.title, "
            "description = excluded.description, tags = excluded.tags, content = excluded.content, "
            "saved_at = excluded.saved_at",
            (doc_id, title or "", description or "", tags or "", content or "", _now()),
        )


def get_draft(db_path: Optional[os.PathLike] = None) -> Optional[dict]:
    with _connect(db_path) as conn:
        return _row(conn.execute("SELECT * FROM draft WHERE id = 1").fetchone())


def clear_draft(db_path: Optional[os.PathLike] = None) -> None:
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM draft")


# ------------------------------------------------------------------ settings
def get_setting(key: str, default: Optional[str] = None,
                db_path: Optional[os.PathLike] = None) -> Optional[str]:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str, db_path: Optional[os.PathLike] = None) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def get_all_settings(db_path: Optional[os.PathLike] = None) -> dict:
    with _connect(db_path) as conn:
        return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}
