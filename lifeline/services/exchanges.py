"""Hospital-to-hospital blood exchange: request -> supplier accepts (units reserved) -> complete (units move)."""
from __future__ import annotations

import sqlite3
from typing import Any

from lifeline import clock
from lifeline.constants import MAX_UNITS_PER_RECEIPT, EventType, ExchangeStatus, UnitStatus
from lifeline.db.connection import transaction
from lifeline.db.repositories import audit
from lifeline.db.repositories import events as events_repo
from lifeline.db.repositories import exchanges as exchanges_repo
from lifeline.db.repositories import units as units_repo
from lifeline.errors import InsufficientStock, NotFound, ValidationError
from lifeline.services import stock
from lifeline.services.common import Actor, authorize_any, authorize_hospital, check_count, check_group, require_hospital

ACTIVE = (ExchangeStatus.PENDING.value, ExchangeStatus.ACCEPTED.value)


def _load(conn: sqlite3.Connection, exchange_id: int) -> dict[str, Any]:
    exchange = exchanges_repo.get(conn, exchange_id)
    if exchange is None:
        raise NotFound(f"Exchange {exchange_id} does not exist.")
    return exchange


def request_exchange(actor: Actor, supplier_id: int, requester_id: int, blood_group: str, units: int) -> int:
    """`requester_id` asks `supplier_id` for units. The requester's staff (or a super admin) files it."""
    authorize_hospital(actor, requester_id)
    check_group(blood_group)
    check_count(units, maximum=MAX_UNITS_PER_RECEIPT)
    if supplier_id == requester_id:
        raise ValidationError("A hospital cannot request blood from itself.")
    with transaction() as conn:
        require_hospital(conn, supplier_id)
        require_hospital(conn, requester_id)
        exchange_id = exchanges_repo.insert(conn, supplier_id=supplier_id, requester_id=requester_id,
                                            blood_group=blood_group, units=units, requested_by=actor.id)
        audit.record(conn, "EXCHANGE_REQUESTED", f"{units}u {blood_group} requested", actor_id=actor.id,
                     entity_type="exchange", entity_id=exchange_id,
                     after={"supplier_id": supplier_id, "requester_id": requester_id, "blood_group": blood_group, "units": units})
    return exchange_id


def respond_exchange(actor: Actor, exchange_id: int, accept: bool) -> None:
    """The supplier accepts (units are reserved for the exchange) or rejects."""
    today = clock.today().isoformat()
    with transaction() as conn:
        exchange = _load(conn, exchange_id)
        authorize_hospital(actor, exchange["from_hospital_id"])
        if exchange["status"] != ExchangeStatus.PENDING.value:
            raise ValidationError(f"Exchange is already {exchange['status'].lower()}.")
        if not accept:
            exchanges_repo.set_status(conn, exchange_id, (ExchangeStatus.PENDING.value,), ExchangeStatus.REJECTED.value,
                                      decided_by=actor.id)
            audit.record(conn, "EXCHANGE_REJECTED", "Exchange rejected", actor_id=actor.id, entity_type="exchange",
                         entity_id=exchange_id, before={"status": "PENDING"}, after={"status": "REJECTED"})
            return
        picked = units_repo.pick_fefo(conn, exchange["from_hospital_id"], exchange["blood_group"], exchange["units"], today)
        if len(picked) < exchange["units"]:
            raise InsufficientStock(exchange["blood_group"], exchange["units"], len(picked))
        units_repo.set_status(conn, [u["id"] for u in picked], UnitStatus.AVAILABLE, UnitStatus.RESERVED,
                              exchange_id=exchange_id)
        events_repo.add_for_units(conn, picked, EventType.RESERVED, actor_id=actor.id, note=f"exchange {exchange_id}")
        exchanges_repo.set_status(conn, exchange_id, (ExchangeStatus.PENDING.value,), ExchangeStatus.ACCEPTED.value,
                                  decided_by=actor.id)
        audit.record(conn, "EXCHANGE_ACCEPTED", f"{len(picked)} unit(s) reserved", actor_id=actor.id,
                     entity_type="exchange", entity_id=exchange_id, before={"status": "PENDING"},
                     after={"status": "ACCEPTED", "unit_codes": [u["unit_code"] for u in picked]})
        stock.refresh_status(conn, exchange["from_hospital_id"])


def complete_exchange(actor: Actor, exchange_id: int) -> None:
    """The reserved units change hands: they become available stock of the requesting hospital."""
    with transaction() as conn:
        exchange = _load(conn, exchange_id)
        authorize_any(actor, exchange["from_hospital_id"], exchange["to_hospital_id"])
        if exchange["status"] != ExchangeStatus.ACCEPTED.value:
            raise ValidationError("Only an accepted exchange can be completed.")
        reserved = units_repo.reserved_for_exchange(conn, exchange_id)
        if len(reserved) != exchange["units"]:
            raise ValidationError(f"Only {len(reserved)} of {exchange['units']} reserved unit(s) remain; cannot complete.")
        ids = [u["id"] for u in reserved]
        units_repo.set_status(conn, ids, UnitStatus.RESERVED, UnitStatus.AVAILABLE)
        units_repo.transfer(conn, ids, exchange["to_hospital_id"])
        events_repo.add_for_units(conn, reserved, EventType.TRANSFERRED_OUT, actor_id=actor.id,
                                  note=f"exchange {exchange_id}", hospital_id=exchange["from_hospital_id"])
        events_repo.add_for_units(conn, reserved, EventType.TRANSFERRED_IN, actor_id=actor.id,
                                  note=f"exchange {exchange_id}", hospital_id=exchange["to_hospital_id"])
        exchanges_repo.set_status(conn, exchange_id, (ExchangeStatus.ACCEPTED.value,), ExchangeStatus.COMPLETED.value)
        audit.record(conn, "EXCHANGE_COMPLETED", f"{len(ids)} unit(s) transferred", actor_id=actor.id,
                     entity_type="exchange", entity_id=exchange_id, before={"status": "ACCEPTED"},
                     after={"status": "COMPLETED", "unit_codes": [u["unit_code"] for u in reserved]})
        stock.refresh_status(conn, exchange["from_hospital_id"])
        stock.refresh_status(conn, exchange["to_hospital_id"])


def cancel_exchange(actor: Actor, exchange_id: int) -> None:
    with transaction() as conn:
        exchange = _load(conn, exchange_id)
        authorize_any(actor, exchange["from_hospital_id"], exchange["to_hospital_id"])
        if exchange["status"] not in ACTIVE:
            raise ValidationError(f"Exchange is already {exchange['status'].lower()}.")
        reserved = units_repo.reserved_for_exchange(conn, exchange_id)
        if reserved:
            units_repo.set_status(conn, [u["id"] for u in reserved], UnitStatus.RESERVED, UnitStatus.AVAILABLE,
                                  clear_reservation=True)
            events_repo.add_for_units(conn, reserved, EventType.RELEASED, actor_id=actor.id,
                                      note=f"exchange {exchange_id} cancelled")
        exchanges_repo.set_status(conn, exchange_id, ACTIVE, ExchangeStatus.CANCELLED.value)
        audit.record(conn, "EXCHANGE_CANCELLED", "Exchange cancelled", actor_id=actor.id, entity_type="exchange",
                     entity_id=exchange_id, before={"status": exchange["status"]},
                     after={"status": "CANCELLED", "released": len(reserved)})
        stock.refresh_status(conn, exchange["from_hospital_id"])
