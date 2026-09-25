"""Numbered SQL migrations tracked with PRAGMA user_version."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from lifeline.config import get_settings
from lifeline.db.connection import connect

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class DatabaseNotInitialised(RuntimeError):
    """The database file is missing or has no users table."""


def _migrations() -> list[tuple[int, Path]]:
    found = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        match = re.match(r"(\d+)_", path.name)
        if match:
            found.append((int(match.group(1)), path))
    return sorted(found)


LATEST_VERSION = max(v for v, _ in _migrations())


def current_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _backup(conn: sqlite3.Connection, version: int) -> None:
    """Copy the database next to itself before its first migration (once per starting version)."""
    file = conn.execute("PRAGMA database_list").fetchone()[2]
    if not file:                                    # in-memory
        return
    target = Path(file + f".bak-v{version}")
    if not target.exists():
        dest = sqlite3.connect(target)
        try:
            conn.backup(dest)
        finally:
            dest.close()


def apply_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply every migration newer than the DB's user_version. Returns the versions applied."""
    applied: list[int] = []
    start = current_version(conn)
    if start < LATEST_VERSION:
        _backup(conn, start)
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        for version, path in _migrations():
            if version > start:
                conn.executescript(path.read_text(encoding="utf-8"))
                applied.append(version)
        if applied and (bad := conn.execute("PRAGMA foreign_key_check").fetchall()):
            raise RuntimeError(f"migration left {len(bad)} foreign key violation(s)")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    return applied


def ensure_schema() -> list[int]:
    """Bring an existing DB up to date; raise DatabaseNotInitialised if there is none."""
    path = get_settings().db_path
    if not path.exists():
        raise DatabaseNotInitialised(f"Database not found at {path}. Run: python setup_database.py")
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'users'").fetchone():
            raise DatabaseNotInitialised("Database has no tables. Run: python setup_database.py")
        applied = apply_migrations(conn)
        conn.execute("PRAGMA journal_mode = WAL")   # persistent; lets several sessions read while one writes
    return applied
