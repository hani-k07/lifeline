# utils/database.py
"""Read-side helpers for the pages (transitional).

Every write now goes through lifeline.services.* (validated, atomic, audited). What is left here are
read queries with the shapes the pages already consume, plus the small auth/audit helpers. Phase 5 rebuilds the
pages on top of services/queries and this module goes away."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from lifeline import clock
from lifeline.constants import BLOOD_GROUPS
from lifeline.db.connection import connect as _conn
from lifeline.db.repositories import audit as audit_repo
from lifeline.db.repositories import contracts as contracts_repo
from lifeline.db.repositories import events as events_repo
from lifeline.db.repositories import exchanges as exchanges_repo
from lifeline.db.repositories import hospitals as hospitals_repo
from lifeline.db.repositories import people
from lifeline.db.repositories import requests as requests_repo
from lifeline.db.repositories import units as units_repo
from lifeline.services.stock import group_level


def _today() -> str:
    return clock.today().isoformat()


# ---------------------------------------------------------------- users / audit
def get_user_by_email(email: str) -> dict | None:
    with _conn() as conn:
        return people.user_by_email(conn, email)


def get_user_by_id(user_id: int) -> dict | None:
    with _conn() as conn:
        return people.user_by_id(conn, user_id)


def get_all_users() -> list[dict]:
    with _conn() as conn:
        return people.users(conn)


def add_user(email: str, password_hash: str, role: str, name: str, hospital_id: int | None = None) -> bool:
    with _conn() as conn:
        return people.user_insert(conn, email, password_hash, role, name, hospital_id)


def update_password_hash(user_id: int, password_hash: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


def add_audit_log(action_type: str, description: str, user_id: int | None = None) -> None:
    with _conn() as conn:
        audit_repo.record(conn, action_type, description, actor_id=user_id)


def get_audit_logs(limit: int = 100) -> list[dict]:
    with _conn() as conn:
        return audit_repo.recent(conn, limit)


def log_ai_usage(feature: str, input_summary: str, response_preview: str,
                 hospital_id: int | None = None, user_id: int | None = None) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO ai_logs (feature, input_summary, response_preview, hospital_id, user_id, created_at) VALUES (?,?,?,?,?,?)",
            (feature, input_summary, response_preview[:200], hospital_id, user_id, clock.now_iso()))


def get_ai_logs(limit: int = 50) -> list[dict]:
    with _conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM ai_logs ORDER BY created_at DESC LIMIT ?", (limit,))]


def get_person_names() -> list[str]:
    with _conn() as conn:
        return people.person_names(conn)


# ---------------------------------------------------------------- hospitals / stock
def get_all_hospitals() -> list[dict]:
    with _conn() as conn:
        return hospitals_repo.all_hospitals(conn)


def get_hospital_by_id(hospital_id: int) -> dict | None:
    with _conn() as conn:
        return hospitals_repo.get(conn, hospital_id)


def get_blood_units(hospital_id: int | None = None) -> list[dict]:
    """Available, unexpired stock grouped by (hospital, group, expiry). Reserved/issued/expired units are not stock."""
    with _conn() as conn:
        return units_repo.grouped_stock(conn, hospital_id, _today())


def get_blood_summary(hospital_id: int | None = None) -> dict[str, int]:
    with _conn() as conn:
        return units_repo.counts_by_group(conn, hospital_id, _today())


def get_expiring_units(hospital_id: int | None, days: int = 3) -> list[dict]:
    today = clock.today()
    with _conn() as conn:
        return units_repo.expiring_within(conn, hospital_id, today.isoformat(), (today + timedelta(days=days)).isoformat())


def get_stock_by_hospital() -> dict[int, dict[str, int]]:
    """hospital_id -> {blood_group: available unexpired units}, for routing."""
    with _conn() as conn:
        return units_repo.totals_by_hospital(conn, _today())


def get_reserved_counts() -> dict[int, int]:
    """request_id -> number of units currently reserved for it."""
    with _conn() as conn:
        return {r[0]: int(r[1]) for r in conn.execute(
            "SELECT request_id, COUNT(*) FROM blood_units WHERE status = 'reserved' AND request_id IS NOT NULL"
            " GROUP BY request_id")}


def get_daily_usage(hospital_id: int | None, blood_group: str | None, days: int = 14) -> list[float]:
    """Units issued/transfused per day (oldest first), from the inventory event ledger."""
    with _conn() as conn:
        return events_repo.daily_usage(conn, hospital_id, blood_group, days, _today())


def get_inventory_events(hospital_id: int | None = None, limit: int = 50) -> list[dict]:
    with _conn() as conn:
        return events_repo.recent(conn, hospital_id, limit)


def get_dashboard_stats(hospital_id: int | None = None) -> dict[str, Any]:
    with _conn() as conn:
        summary = units_repo.counts_by_group(conn, hospital_id, _today())
        donors = people.donors(conn, hospital_id)
        requests = requests_repo.listing(conn, hospital_id)
    return {
        "total_units": sum(summary.values()),
        "total_donors": len(donors),
        "pending_requests": sum(1 for r in requests if r["status"] in ("PENDING", "RESERVED")),
        "critical_groups": [g for g in BLOOD_GROUPS if group_level(summary.get(g, 0)) == "critical"],
        "blood_summary": summary,
    }


# ---------------------------------------------------------------- operations (read)
def get_donors(hospital_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        return people.donors(conn, hospital_id)


def get_blood_requests(hospital_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        return requests_repo.listing(conn, hospital_id)


def get_transfusions(hospital_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        return people.transfusions(conn, hospital_id)


def get_exchanges(hospital_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        return exchanges_repo.listing(conn, hospital_id)


def get_contracts(hospital_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        return contracts_repo.listing(conn, hospital_id)


def get_screening_tests(hospital_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        return people.screenings(conn, hospital_id)
