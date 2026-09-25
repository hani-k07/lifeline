"""Create a brand-new database from schema.sql at the latest version."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from lifeline.db.migrate import LATEST_VERSION

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(f"PRAGMA user_version = {LATEST_VERSION}")   # a fresh schema already includes every migration
    conn.commit()
