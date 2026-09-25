from __future__ import annotations

import json
import sqlite3
from typing import Any

from lifeline import clock


def _dump(value: Any) -> str | None:
    return None if value is None else json.dumps(value, default=str, sort_keys=True)


def record(conn: sqlite3.Connection, action_type: str, description: str, *, actor_id: int | None = None,
           entity_type: str | None = None, entity_id: object = None, before: Any = None, after: Any = None) -> None:
    """Append one audit row (PKT timestamp). Call it on the same connection as the change it describes."""
    conn.execute(
        "INSERT INTO audit_logs (action_type, description, user_id, timestamp, entity_type, entity_id, before_json, after_json)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (action_type, description, actor_id, clock.now_iso(), entity_type,
         None if entity_id is None else str(entity_id), _dump(before), _dump(after)),
    )


def recent(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT al.*, u.name AS user_name FROM audit_logs al LEFT JOIN users u ON al.user_id = u.id "
        "ORDER BY al.timestamp DESC, al.id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def for_entity(conn: sqlite3.Connection, entity_type: str, entity_id: object) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM audit_logs WHERE entity_type = ? AND entity_id = ? ORDER BY id",
                        (entity_type, str(entity_id))).fetchall()
    return [dict(r) for r in rows]
