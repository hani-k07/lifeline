from __future__ import annotations

import sqlite3
from typing import Any

from lifeline import clock


def insert(conn: sqlite3.Connection, *, hospital_id: int, blood_group: str, units: int, urgency: str,
           patient_name: str | None, condition: str | None, created_by: int | None) -> int:
    cur = conn.execute(
        "INSERT INTO blood_requests (requesting_hospital_id, blood_group, units_needed, urgency, status, patient_name,"
        " patient_condition, created_at, created_by) VALUES (?,?,?,?, 'PENDING', ?,?,?,?)",
        (hospital_id, blood_group, units, urgency, patient_name, condition, clock.now_iso(), created_by))
    assert cur.lastrowid is not None
    return cur.lastrowid


def get(conn: sqlite3.Connection, request_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM blood_requests WHERE id = ?", (request_id,)).fetchone()
    return dict(row) if row else None


def set_status(conn: sqlite3.Connection, request_id: int, expected: tuple[str, ...], new: str) -> bool:
    marks = ",".join("?" * len(expected))
    resolved = clock.now_iso() if new in ("RESOLVED", "CANCELLED") else None
    return conn.execute(
        f"UPDATE blood_requests SET status = ?, resolved_at = COALESCE(?, resolved_at) WHERE id = ? AND status IN ({marks})",
        (new, resolved, request_id, *expected)).rowcount == 1


def listing(conn: sqlite3.Connection, hospital_id: int | None) -> list[dict[str, Any]]:
    sql = ("SELECT br.*, h.name AS hospital_name FROM blood_requests br"
           " JOIN hospitals h ON br.requesting_hospital_id = h.id"
           + (" WHERE br.requesting_hospital_id = ?" if hospital_id is not None else "")
           + " ORDER BY br.created_at DESC, br.id DESC")
    return [dict(r) for r in conn.execute(sql, (hospital_id,) if hospital_id is not None else ())]
