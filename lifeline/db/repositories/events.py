from __future__ import annotations

import sqlite3
from typing import Any

from lifeline import clock
from lifeline.constants import EventType


def add(conn: sqlite3.Connection, *, hospital_id: int, blood_group: str, event_type: EventType,
        unit_id: int | None = None, request_id: int | None = None, actor_id: int | None = None,
        note: str | None = None) -> None:
    conn.execute(
        "INSERT INTO inventory_events (at, unit_id, hospital_id, blood_group, event_type, request_id, actor_id, note)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (clock.now_iso(), unit_id, hospital_id, blood_group, event_type.value, request_id, actor_id, note))


def add_for_units(conn: sqlite3.Connection, units: list[dict[str, Any]], event_type: EventType, *,
                  actor_id: int | None, request_id: int | None = None, note: str | None = None,
                  hospital_id: int | None = None) -> None:
    for unit in units:
        add(conn, hospital_id=hospital_id or unit["hospital_id"], blood_group=unit["blood_group"],
            event_type=event_type, unit_id=unit["id"], request_id=request_id, actor_id=actor_id, note=note)


def recent(conn: sqlite3.Connection, hospital_id: int | None, limit: int = 50) -> list[dict[str, Any]]:
    sql = "SELECT * FROM inventory_events" + (" WHERE hospital_id = ?" if hospital_id is not None else "")
    args: tuple[Any, ...] = (hospital_id, limit) if hospital_id is not None else (limit,)
    return [dict(r) for r in conn.execute(sql + " ORDER BY at DESC, id DESC LIMIT ?", args)]


def daily_usage(conn: sqlite3.Connection, hospital_id: int | None, blood_group: str | None, days: int,
                today: str) -> list[float]:
    """Units that left stock for patients (issued or transfused) per day for the last `days` days, oldest first.
    Days with no movement are 0, so the series is dense and ready for forecasting."""
    sql = ("SELECT substr(at, 1, 10) AS day, COUNT(*) AS n FROM inventory_events WHERE event_type IN ('issued','transfused')"
           " AND substr(at, 1, 10) > date(?, ?) AND substr(at, 1, 10) <= ?")
    args: list[Any] = [today, f"-{days} days", today]
    if hospital_id is not None:
        sql += " AND hospital_id = ?"
        args.append(hospital_id)
    if blood_group is not None:
        sql += " AND blood_group = ?"
        args.append(blood_group)
    per_day = {r["day"]: r["n"] for r in conn.execute(sql + " GROUP BY day", args)}
    out: list[float] = []
    for offset in range(days - 1, -1, -1):
        day = conn.execute("SELECT date(?, ?)", (today, f"-{offset} days")).fetchone()[0]
        out.append(float(per_day.get(day, 0)))
    return out
