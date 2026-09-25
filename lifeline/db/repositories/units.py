from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Sequence
from typing import Any

from lifeline import clock
from lifeline.constants import UnitStatus
from lifeline.errors import InvalidTransition


def insert(conn: sqlite3.Connection, hospital_id: int, blood_group: str, count: int, *, collected_at: str,
           expiry_date: str, donor_id: int | None = None) -> list[int]:
    """Create `count` available units and give each a readable code (U0000123)."""
    now = clock.now_iso()
    ids: list[int] = []
    for _ in range(count):
        cur = conn.execute(
            "INSERT INTO blood_units (unit_code, hospital_id, blood_group, donor_id, collected_at, expiry_date, status,"
            " status_changed_at, created_at) VALUES (?,?,?,?,?,?,'available',?,?)",
            (f"tmp-{uuid.uuid4().hex}", hospital_id, blood_group, donor_id, collected_at, expiry_date, now, now))
        assert cur.lastrowid is not None
        ids.append(cur.lastrowid)
    conn.executemany("UPDATE blood_units SET unit_code = ? WHERE id = ?", [(f"U{i:07d}", i) for i in ids])
    return ids


def pick_fefo(conn: sqlite3.Connection, hospital_id: int, blood_group: str, count: int, today: str) -> list[dict[str, Any]]:
    """The `count` available, unexpired units that expire first (First-Expired-First-Out)."""
    rows = conn.execute(
        "SELECT * FROM blood_units WHERE hospital_id = ? AND blood_group = ? AND status = 'available' AND expiry_date >= ?"
        " ORDER BY expiry_date, id LIMIT ?", (hospital_id, blood_group, today, count)).fetchall()
    return [dict(r) for r in rows]


def count_available(conn: sqlite3.Connection, hospital_id: int, blood_group: str, today: str) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) FROM blood_units WHERE hospital_id = ? AND blood_group = ? AND status = 'available'"
        " AND expiry_date >= ?", (hospital_id, blood_group, today)).fetchone()[0])


def set_status(conn: sqlite3.Connection, unit_ids: Sequence[int], expected: UnitStatus, new: UnitStatus, *,
               request_id: int | None = None, exchange_id: int | None = None, transfusion_id: int | None = None,
               clear_reservation: bool = False) -> None:
    """Move units `expected` -> `new`. The UPDATE only matches units still in `expected`, so a unit that another
    caller already took is detected (rowcount 0) instead of being handed out twice."""
    now = clock.now_iso()
    for unit_id in unit_ids:
        sets = ["status = ?", "status_changed_at = ?"]
        args: list[Any] = [new.value, now]
        if request_id is not None:
            sets.append("request_id = ?")
            args.append(request_id)
        if exchange_id is not None:
            sets.append("exchange_id = ?")
            args.append(exchange_id)
        if transfusion_id is not None:
            sets.append("transfusion_id = ?")
            args.append(transfusion_id)
        if clear_reservation:
            sets += ["request_id = NULL", "exchange_id = NULL"]
        cur = conn.execute(f"UPDATE blood_units SET {', '.join(sets)} WHERE id = ? AND status = ?",
                           (*args, unit_id, expected.value))
        if cur.rowcount != 1:
            raise InvalidTransition(f"unit {unit_id} is no longer {expected.value}")


def transfer(conn: sqlite3.Connection, unit_ids: Sequence[int], to_hospital_id: int) -> None:
    now = clock.now_iso()
    for unit_id in unit_ids:
        conn.execute("UPDATE blood_units SET hospital_id = ?, status_changed_at = ? WHERE id = ?",
                     (to_hospital_id, now, unit_id))


def reserved_for_request(conn: sqlite3.Connection, request_id: int) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM blood_units WHERE request_id = ? AND status = 'reserved' ORDER BY expiry_date, id", (request_id,))]


def reserved_for_exchange(conn: sqlite3.Connection, exchange_id: int) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM blood_units WHERE exchange_id = ? AND status = 'reserved' ORDER BY expiry_date, id", (exchange_id,))]


def get(conn: sqlite3.Connection, unit_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM blood_units WHERE id = ?", (unit_id,)).fetchone()
    return dict(row) if row else None


def due_for_expiry(conn: sqlite3.Connection, today: str) -> list[dict[str, Any]]:
    """Available or reserved units whose expiry date has passed."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM blood_units WHERE status IN ('available','reserved') AND expiry_date < ? ORDER BY id", (today,))]


def counts_by_group(conn: sqlite3.Connection, hospital_id: int | None, today: str) -> dict[str, int]:
    sql = ("SELECT blood_group, COUNT(*) FROM blood_units WHERE status = 'available' AND expiry_date >= ?"
           + (" AND hospital_id = ?" if hospital_id is not None else "") + " GROUP BY blood_group")
    args: tuple[Any, ...] = (today, hospital_id) if hospital_id is not None else (today,)
    return {r[0]: int(r[1]) for r in conn.execute(sql, args)}


def totals_by_hospital(conn: sqlite3.Connection, today: str) -> dict[int, dict[str, int]]:
    out: dict[int, dict[str, int]] = {}
    for hospital_id, group, n in conn.execute(
            "SELECT hospital_id, blood_group, COUNT(*) FROM blood_units WHERE status = 'available' AND expiry_date >= ?"
            " GROUP BY hospital_id, blood_group", (today,)):
        out.setdefault(hospital_id, {})[group] = int(n)
    return out


def grouped_stock(conn: sqlite3.Connection, hospital_id: int | None, today: str) -> list[dict[str, Any]]:
    """Available stock grouped by (hospital, group, expiry): the shape the stock tables/graph consume."""
    sql = ("SELECT MIN(u.id) AS id, u.hospital_id, h.name AS hospital_name, u.blood_group, u.expiry_date,"
           " COUNT(*) AS units, MAX(u.status_changed_at) AS updated_at FROM blood_units u"
           " JOIN hospitals h ON h.id = u.hospital_id WHERE u.status = 'available' AND u.expiry_date >= ?"
           + (" AND u.hospital_id = ?" if hospital_id is not None else "")
           + " GROUP BY u.hospital_id, u.blood_group, u.expiry_date ORDER BY u.expiry_date, u.blood_group")
    args: tuple[Any, ...] = (today, hospital_id) if hospital_id is not None else (today,)
    return [dict(r) for r in conn.execute(sql, args)]


def expiring_within(conn: sqlite3.Connection, hospital_id: int | None, today: str, until: str) -> list[dict[str, Any]]:
    sql = ("SELECT u.*, h.name AS hospital_name FROM blood_units u JOIN hospitals h ON h.id = u.hospital_id"
           " WHERE u.status = 'available' AND u.expiry_date >= ? AND u.expiry_date <= ?"
           + (" AND u.hospital_id = ?" if hospital_id is not None else "") + " ORDER BY u.expiry_date, u.id")
    args: tuple[Any, ...] = (today, until, hospital_id) if hospital_id is not None else (today, until)
    return [dict(r) for r in conn.execute(sql, args)]
