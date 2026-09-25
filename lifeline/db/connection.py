"""SQLite connection factory (foreign keys on, rows as mappings, closed after each `with`)."""
from __future__ import annotations

import sqlite3
from typing import Any, Literal

from lifeline.config import get_settings


class _Connection(sqlite3.Connection):
    """`with connect() as conn:` commits/rolls back like sqlite3 does, then also closes."""

    def __exit__(self, *exc_info: Any) -> Literal[False]:
        try:
            return super().__exit__(*exc_info)
        finally:
            self.close()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(get_settings().db_path, factory=_Connection, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
