"""SQLite storage: one file, created on first start."""
import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    phone        TEXT    NOT NULL,
    group_name   TEXT    NOT NULL,
    monthly_fee  INTEGER NOT NULL CHECK (monthly_fee > 0)
);

CREATE TABLE IF NOT EXISTS payments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    amount      INTEGER NOT NULL CHECK (amount > 0),
    paid_on     TEXT    NOT NULL,          -- YYYY-MM-DD
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS payments_student_date ON payments (student_id, paid_on);
"""


def db_path() -> str:
    return os.environ.get("DB_PATH", str(Path(__file__).resolve().parent.parent / "data.sqlite3"))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def get_conn():
    """FastAPI dependency: one connection per request, committed on success."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
