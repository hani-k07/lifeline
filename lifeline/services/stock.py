"""Stock levels and the derived hospitals.stock_status."""
from __future__ import annotations

import sqlite3

from lifeline import clock
from lifeline.constants import (
    BLOOD_GROUPS,
    CRITICAL_UNITS,
    HOSPITAL_CRITICAL_TOTAL,
    HOSPITAL_LOW_TOTAL,
    KEY_GROUPS,
    LOW_UNITS,
)
from lifeline.db.repositories import hospitals as hospitals_repo
from lifeline.db.repositories import units as units_repo


def group_level(count: int) -> str:
    """Per blood group at one hospital."""
    if count < CRITICAL_UNITS:
        return "critical"
    return "low" if count < LOW_UNITS else "ok"


def hospital_status(counts_by_group: dict[str, int]) -> str:
    """Whole hospital. critical: very little stock overall, or a KEY group is critical.
    low: modest stock, any group critical, or a KEY group is low. Otherwise ok."""
    total = sum(counts_by_group.values())
    levels = {g: group_level(counts_by_group.get(g, 0)) for g in BLOOD_GROUPS}
    if total < HOSPITAL_CRITICAL_TOTAL or any(levels[g] == "critical" for g in KEY_GROUPS):
        return "critical"
    if total < HOSPITAL_LOW_TOTAL or "critical" in levels.values() or any(levels[g] == "low" for g in KEY_GROUPS):
        return "low"
    return "ok"


def refresh_status(conn: sqlite3.Connection, hospital_id: int) -> str:
    status = hospital_status(units_repo.counts_by_group(conn, hospital_id, clock.today().isoformat()))
    hospitals_repo.set_stock_status(conn, hospital_id, status)
    return status
