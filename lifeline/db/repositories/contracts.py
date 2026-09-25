from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from lifeline import clock


def insert(conn: sqlite3.Connection, *, lender_id: int, borrower_id: int, blood_group: str, units: int,
           return_deadline: str, created_by: int | None) -> int:
    cur = conn.execute(
        "INSERT INTO contracts (ticket_id, lending_hospital_id, borrowing_hospital_id, blood_group, units, created_at,"
        " return_deadline, status, created_by) VALUES (?,?,?,?,?,?,?, 'ACTIVE', ?)",
        (f"tmp-{uuid.uuid4().hex}", lender_id, borrower_id, blood_group, units, clock.now_iso(), return_deadline, created_by))
    contract_id = cur.lastrowid
    assert contract_id is not None
    conn.execute("UPDATE contracts SET ticket_id = ? WHERE id = ?", (f"LF-{clock.today().year}-{contract_id:04d}", contract_id))
    return contract_id


def get(conn: sqlite3.Connection, contract_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM contracts WHERE id = ?", (contract_id,)).fetchone()
    return dict(row) if row else None


def set_status(conn: sqlite3.Connection, contract_id: int, expected: tuple[str, ...], new: str) -> bool:
    marks = ",".join("?" * len(expected))
    returned = clock.now_iso() if new == "RETURNED" else None
    return conn.execute(
        f"UPDATE contracts SET status = ?, returned_at = COALESCE(?, returned_at) WHERE id = ? AND status IN ({marks})",
        (new, returned, contract_id, *expected)).rowcount == 1


def overdue_active(conn: sqlite3.Connection, now_iso: str) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM contracts WHERE status = 'ACTIVE' AND return_deadline < ? ORDER BY id", (now_iso,))]


def listing(conn: sqlite3.Connection, hospital_id: int | None) -> list[dict[str, Any]]:
    sql = ("SELECT c.*, hl.name AS lender_name, hb.name AS borrower_name FROM contracts c"
           " JOIN hospitals hl ON c.lending_hospital_id = hl.id JOIN hospitals hb ON c.borrowing_hospital_id = hb.id"
           + (" WHERE c.lending_hospital_id = ? OR c.borrowing_hospital_id = ?" if hospital_id is not None else "")
           + " ORDER BY c.return_deadline, c.id")
    return [dict(r) for r in conn.execute(sql, (hospital_id, hospital_id) if hospital_id is not None else ())]
