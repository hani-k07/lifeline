from __future__ import annotations

import sqlite3
from typing import Any


def all_hospitals(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM hospitals ORDER BY id")]


def get(conn: sqlite3.Connection, hospital_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM hospitals WHERE id = ?", (hospital_id,)).fetchone()
    return dict(row) if row else None


def set_stock_status(conn: sqlite3.Connection, hospital_id: int, status: str) -> bool:
    """Returns True if the stored status changed."""
    return conn.execute("UPDATE hospitals SET stock_status = ? WHERE id = ? AND stock_status <> ?",
                        (status, hospital_id, status)).rowcount == 1
