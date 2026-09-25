"""Work the system does by itself: expire old units, flag overdue loans, refresh hospital stock status."""
from __future__ import annotations

from dataclasses import dataclass

from lifeline import clock
from lifeline.constants import ContractStatus, EventType, UnitStatus
from lifeline.db.connection import transaction
from lifeline.db.repositories import audit
from lifeline.db.repositories import contracts as contracts_repo
from lifeline.db.repositories import events as events_repo
from lifeline.db.repositories import hospitals as hospitals_repo
from lifeline.db.repositories import units as units_repo
from lifeline.services import stock
from lifeline.services.common import SYSTEM


@dataclass(frozen=True)
class HousekeepingResult:
    expired_units: int
    breached_contracts: int
    status_changes: int


def run() -> HousekeepingResult:
    """Idempotent; safe to call on every page load."""
    today = clock.today().isoformat()
    now_iso = clock.now_iso()
    with transaction() as conn:
        due = units_repo.due_for_expiry(conn, today)
        for unit in due:
            units_repo.set_status(conn, [unit["id"]], UnitStatus(unit["status"]), UnitStatus.EXPIRED)
        events_repo.add_for_units(conn, due, EventType.EXPIRED, actor_id=SYSTEM.id, note="past expiry date")
        if due:
            audit.record(conn, "UNITS_EXPIRED", f"{len(due)} unit(s) passed their expiry date", actor_id=SYSTEM.id,
                         entity_type="blood_unit", after={"unit_ids": [u["id"] for u in due]})

        overdue = contracts_repo.overdue_active(conn, now_iso)
        for contract in overdue:
            contracts_repo.set_status(conn, contract["id"], (ContractStatus.ACTIVE.value,), ContractStatus.BREACHED.value)
            audit.record(conn, "CONTRACT_BREACHED", f"Loan {contract['ticket_id']} passed its return deadline",
                         actor_id=SYSTEM.id, entity_type="contract", entity_id=contract["id"],
                         before={"status": "ACTIVE"}, after={"status": "BREACHED"})

        changes = sum(stock.refresh_status(conn, h["id"]) != h["stock_status"] for h in hospitals_repo.all_hospitals(conn))
    return HousekeepingResult(len(due), len(overdue), changes)
