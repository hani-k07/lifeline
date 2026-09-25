from __future__ import annotations

import sqlite3
from typing import Any

from lifeline import clock


def insert(conn: sqlite3.Connection, *, supplier_id: int, requester_id: int, blood_group: str, units: int,
           requested_by: int | None) -> int:
    cur = conn.execute(
        "INSERT INTO exchanges (from_hospital_id, to_hospital_id, blood_group, units, status, created_at, requested_by)"
        " VALUES (?,?,?,?, 'PENDING', ?, ?)", (supplier_id, requester_id, blood_group, units, clock.now_iso(), requested_by))
    assert cur.lastrowid is not None
    return cur.lastrowid


def get(conn: sqlite3.Connection, exchange_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM exchanges WHERE id = ?", (exchange_id,)).fetchone()
    return dict(row) if row else None


def set_status(conn: sqlite3.Connection, exchange_id: int, expected: tuple[str, ...], new: str, *,
               decided_by: int | None = None) -> bool:
    marks = ",".join("?" * len(expected))
    completed = clock.now_iso() if new == "COMPLETED" else None
    return conn.execute(
        f"UPDATE exchanges SET status = ?, completed_at = COALESCE(?, completed_at), decided_by = COALESCE(?, decided_by)"
        f" WHERE id = ? AND status IN ({marks})", (new, completed, decided_by, exchange_id, *expected)).rowcount == 1


def listing(conn: sqlite3.Connection, hospital_id: int | None) -> list[dict[str, Any]]:
    sql = ("SELECT e.*, hf.name AS from_name, ht.name AS to_name FROM exchanges e"
           " JOIN hospitals hf ON e.from_hospital_id = hf.id JOIN hospitals ht ON e.to_hospital_id = ht.id"
           + (" WHERE e.from_hospital_id = ? OR e.to_hospital_id = ?" if hospital_id is not None else "")
           + " ORDER BY e.created_at DESC, e.id DESC")
    return [dict(r) for r in conn.execute(sql, (hospital_id, hospital_id) if hospital_id is not None else ())]
