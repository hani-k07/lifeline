from __future__ import annotations

from datetime import date

from lifeline import clock
from lifeline.constants import MAX_UNITS_PER_RECEIPT, EventType, UnitStatus
from lifeline.db.connection import transaction
from lifeline.db.repositories import audit
from lifeline.db.repositories import events as events_repo
from lifeline.db.repositories import units as units_repo
from lifeline.errors import InsufficientStock, InvalidTransition, NotFound, ValidationError
from lifeline.services import stock
from lifeline.services.common import Actor, authorize_hospital, check_count, check_group, require_hospital

MAX_SHELF_LIFE_DAYS = 60     # nothing red-cell based lasts longer; a later date is a typo


def receive_units(actor: Actor, hospital_id: int, blood_group: str, count: int, expiry_date: date, *,
                  collected_at: date | None = None, donor_id: int | None = None) -> list[int]:
    """Add `count` new units to a hospital's stock. Returns the new unit ids."""
    authorize_hospital(actor, hospital_id)
    check_group(blood_group)
    check_count(count, maximum=MAX_UNITS_PER_RECEIPT)
    today = clock.today()
    collected = collected_at or today
    if collected > today:
        raise ValidationError("Collection date cannot be in the future.")
    if expiry_date <= today:
        raise ValidationError("These units are already expired and cannot be added to stock.")
    if (expiry_date - collected).days > MAX_SHELF_LIFE_DAYS:
        raise ValidationError(f"Expiry date is more than {MAX_SHELF_LIFE_DAYS} days after collection - please check it.")
    with transaction() as conn:
        require_hospital(conn, hospital_id)
        ids = units_repo.insert(conn, hospital_id, blood_group, count, collected_at=collected.isoformat(),
                                expiry_date=expiry_date.isoformat(), donor_id=donor_id)
        events_repo.add_for_units(conn, [{"id": i, "hospital_id": hospital_id, "blood_group": blood_group} for i in ids],
                                  EventType.RECEIVED, actor_id=actor.id)
        audit.record(conn, "STOCK_RECEIVED", f"{count} unit(s) of {blood_group} received", actor_id=actor.id,
                     entity_type="hospital_stock", entity_id=hospital_id,
                     after={"blood_group": blood_group, "count": count, "expiry": expiry_date.isoformat(), "unit_ids": ids})
        stock.refresh_status(conn, hospital_id)
    return ids


def issue_units(actor: Actor, hospital_id: int, blood_group: str, count: int, reason: str = "") -> list[str]:
    """Take `count` units out of stock (First-Expired-First-Out). All or nothing. Returns the unit codes."""
    authorize_hospital(actor, hospital_id)
    check_group(blood_group)
    check_count(count, maximum=MAX_UNITS_PER_RECEIPT)
    today = clock.today().isoformat()
    with transaction() as conn:
        require_hospital(conn, hospital_id)
        picked = units_repo.pick_fefo(conn, hospital_id, blood_group, count, today)
        if len(picked) < count:
            raise InsufficientStock(blood_group, count, len(picked))
        ids = [u["id"] for u in picked]
        units_repo.set_status(conn, ids, UnitStatus.AVAILABLE, UnitStatus.ISSUED)
        events_repo.add_for_units(conn, picked, EventType.ISSUED, actor_id=actor.id, note=reason or None)
        audit.record(conn, "STOCK_ISSUED", f"{count} unit(s) of {blood_group} issued", actor_id=actor.id,
                     entity_type="hospital_stock", entity_id=hospital_id,
                     before={"available": units_repo.count_available(conn, hospital_id, blood_group, today) + count},
                     after={"blood_group": blood_group, "unit_ids": ids, "reason": reason})
        stock.refresh_status(conn, hospital_id)
    return [u["unit_code"] for u in picked]


def discard_unit(actor: Actor, unit_id: int, reason: str) -> None:
    """Write a unit off (damaged, cold-chain break, ...). A reason is mandatory."""
    if not reason.strip():
        raise ValidationError("A reason is required to discard a unit.")
    with transaction() as conn:
        unit = units_repo.get(conn, unit_id)
        if unit is None:
            raise NotFound(f"Unit {unit_id} does not exist.")
        authorize_hospital(actor, unit["hospital_id"])
        current = UnitStatus(unit["status"])
        if current not in (UnitStatus.AVAILABLE, UnitStatus.RESERVED, UnitStatus.ISSUED):
            raise InvalidTransition(f"Unit {unit['unit_code']} is already {current.value}.")
        units_repo.set_status(conn, [unit_id], current, UnitStatus.DISCARDED)
        events_repo.add_for_units(conn, [unit], EventType.DISCARDED, actor_id=actor.id, note=reason)
        audit.record(conn, "UNIT_DISCARDED", f"Unit {unit['unit_code']} discarded", actor_id=actor.id,
                     entity_type="blood_unit", entity_id=unit_id, before={"status": current.value},
                     after={"status": "discarded", "reason": reason})
        stock.refresh_status(conn, unit["hospital_id"])
