"""SQLite connection factory (foreign keys on, rows as mappings, closed after each `with`)."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
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


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """One atomic unit of work. BEGIN IMMEDIATE takes the write lock up front, so a "check status, then update"
    sequence cannot interleave with another writer (this is what makes double-issuing impossible)."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
