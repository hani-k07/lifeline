"""Emergency blood requests: create -> reserve units (possibly at other hospitals) -> fulfil, or cancel."""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import Any

from lifeline import clock
from lifeline.constants import MAX_UNITS_PER_RECEIPT, EventType, RequestStatus, UnitStatus, Urgency
from lifeline.db.connection import transaction
from lifeline.db.repositories import audit
from lifeline.db.repositories import events as events_repo
from lifeline.db.repositories import requests as requests_repo
from lifeline.db.repositories import units as units_repo
from lifeline.engine.compatibility import can_donate
from lifeline.errors import IncompatibleBlood, InsufficientStock, NotFound, ValidationError
from lifeline.services import stock
from lifeline.services.common import Actor, authorize_hospital, check_count, check_group, require_hospital

OPEN = (RequestStatus.PENDING.value, RequestStatus.RESERVED.value)


def _load(conn: sqlite3.Connection, request_id: int, actor: Actor) -> dict[str, Any]:
    request = requests_repo.get(conn, request_id)
    if request is None:
        raise NotFound(f"Request {request_id} does not exist.")
    authorize_hospital(actor, request["requesting_hospital_id"])
    return request


def create_request(actor: Actor, hospital_id: int, blood_group: str, units: int, urgency: str,
                   patient_name: str, condition: str = "") -> int:
    authorize_hospital(actor, hospital_id)
    check_group(blood_group)
    check_count(units, maximum=50)
    if urgency not in {u.value for u in Urgency}:
        raise ValidationError("Choose an urgency level.")
    if not patient_name.strip():
        raise ValidationError("Patient name is required.")
    with transaction() as conn:
        require_hospital(conn, hospital_id)
        request_id = requests_repo.insert(conn, hospital_id=hospital_id, blood_group=blood_group, units=units,
                                          urgency=urgency, patient_name=patient_name.strip(),
                                          condition=condition.strip() or None, created_by=actor.id)
        audit.record(conn, "EMERGENCY_REQUEST", f"{urgency} request for {units}u {blood_group}", actor_id=actor.id,
                     entity_type="request", entity_id=request_id,
                     after={"hospital_id": hospital_id, "blood_group": blood_group, "units": units, "urgency": urgency})
    return request_id


def _reserve_locked(conn: sqlite3.Connection, actor: Actor, request: dict[str, Any], source_hospital_id: int,
                    unit_blood_group: str, count: int, today: str) -> list[dict[str, Any]]:
    """Reserve `count` units inside an open transaction (shared by reserve_units and create_and_reserve)."""
    request_id = request["id"]
    if request["status"] not in OPEN:
        raise ValidationError(f"Request is {request['status'].lower()}; units cannot be reserved for it.")
    require_hospital(conn, source_hospital_id)
    if not can_donate(unit_blood_group, request["blood_group"]):
        raise IncompatibleBlood(unit_blood_group, request["blood_group"])
    already = len(units_repo.reserved_for_request(conn, request_id))
    if already + count > request["units_needed"]:
        raise ValidationError(f"Request needs {request['units_needed']} unit(s); {already} already reserved.")
    picked = units_repo.pick_fefo(conn, source_hospital_id, unit_blood_group, count, today)
    if len(picked) < count:
        raise InsufficientStock(unit_blood_group, count, len(picked))
    units_repo.set_status(conn, [u["id"] for u in picked], UnitStatus.AVAILABLE, UnitStatus.RESERVED, request_id=request_id)
    events_repo.add_for_units(conn, picked, EventType.RESERVED, actor_id=actor.id, request_id=request_id)
    requests_repo.set_status(conn, request_id, OPEN, RequestStatus.RESERVED.value)
    audit.record(conn, "REQUEST_RESERVED", f"{count} unit(s) of {unit_blood_group} reserved", actor_id=actor.id,
                 entity_type="request", entity_id=request_id, before={"reserved": already},
                 after={"reserved": already + count, "source_hospital_id": source_hospital_id,
                        "unit_codes": [u["unit_code"] for u in picked]})
    stock.refresh_status(conn, source_hospital_id)
    return picked


def reserve_units(actor: Actor, request_id: int, source_hospital_id: int, unit_blood_group: str, count: int) -> list[str]:
    """Reserve `count` compatible units at `source_hospital_id` for the request (First-Expired-First-Out).
    Can be called several times to draw from several hospitals; the total can never exceed the units needed."""
    check_group(unit_blood_group)
    check_count(count, maximum=MAX_UNITS_PER_RECEIPT)
    with transaction() as conn:
        request = _load(conn, request_id, actor)
        picked = _reserve_locked(conn, actor, request, source_hospital_id, unit_blood_group, count, clock.today().isoformat())
    return [u["unit_code"] for u in picked]


def create_and_reserve(actor: Actor, hospital_id: int, blood_group: str, units: int, urgency: str, patient_name: str,
                       condition: str, sources: Sequence[tuple[int, str, int]]) -> tuple[int, list[str]]:
    """The emergency flow's confirm step, atomically: create the request AND reserve every chosen unit AND audit both.
    `sources` are (source hospital id, unit blood group, count); together they must cover exactly `units`. If anything
    fails - stock changed since the search, an incompatible group - nothing at all is written."""
    authorize_hospital(actor, hospital_id)
    check_group(blood_group)
    check_count(units, maximum=50)
    if urgency not in {u.value for u in Urgency}:
        raise ValidationError("Choose an urgency level.")
    if not patient_name.strip():
        raise ValidationError("Patient name is required.")
    if sum(count for _, _, count in sources) != units:
        raise ValidationError(f"The chosen sources must cover exactly {units} unit(s).")
    for _, group, count in sources:
        check_group(group)
        check_count(count, maximum=MAX_UNITS_PER_RECEIPT)
    today = clock.today().isoformat()
    codes: list[str] = []
    with transaction() as conn:
        require_hospital(conn, hospital_id)
        request_id = requests_repo.insert(conn, hospital_id=hospital_id, blood_group=blood_group, units=units,
                                          urgency=urgency, patient_name=patient_name.strip(),
                                          condition=condition.strip() or None, created_by=actor.id)
        audit.record(conn, "EMERGENCY_REQUEST", f"{urgency} request for {units}u {blood_group}", actor_id=actor.id,
                     entity_type="request", entity_id=request_id,
                     after={"hospital_id": hospital_id, "blood_group": blood_group, "units": units, "urgency": urgency})
        for source_id, group, count in sources:
            request = requests_repo.get(conn, request_id)
            assert request is not None
            codes += [u["unit_code"] for u in _reserve_locked(conn, actor, request, source_id, group, count, today)]
    return request_id, codes


def fulfil_request(actor: Actor, request_id: int) -> None:
    """Dispatch the reserved units: they become 'issued' and the request is resolved."""
    with transaction() as conn:
        request = _load(conn, request_id, actor)
        if request["status"] != RequestStatus.RESERVED.value:
            raise ValidationError("Reserve units for this request before fulfilling it.")
        reserved = units_repo.reserved_for_request(conn, request_id)
        if len(reserved) != request["units_needed"]:
            raise ValidationError(f"{len(reserved)} of {request['units_needed']} unit(s) reserved - reserve the rest first.")
        units_repo.set_status(conn, [u["id"] for u in reserved], UnitStatus.RESERVED, UnitStatus.ISSUED)
        events_repo.add_for_units(conn, reserved, EventType.ISSUED, actor_id=actor.id, request_id=request_id,
                                  note=f"to hospital {request['requesting_hospital_id']}")
        requests_repo.set_status(conn, request_id, (RequestStatus.RESERVED.value,), RequestStatus.RESOLVED.value)
        audit.record(conn, "REQUEST_FULFILLED", f"Request {request_id} fulfilled", actor_id=actor.id,
                     entity_type="request", entity_id=request_id, before={"status": "RESERVED"},
                     after={"status": "RESOLVED", "unit_codes": [u["unit_code"] for u in reserved]})
        for hospital_id in {u["hospital_id"] for u in reserved}:
            stock.refresh_status(conn, hospital_id)


def cancel_request(actor: Actor, request_id: int, reason: str = "") -> None:
    """Cancel an open request and put every reserved unit back into stock."""
    with transaction() as conn:
        request = _load(conn, request_id, actor)
        if request["status"] not in OPEN:
            raise ValidationError(f"Request is already {request['status'].lower()}.")
        reserved = units_repo.reserved_for_request(conn, request_id)
        if reserved:
            units_repo.set_status(conn, [u["id"] for u in reserved], UnitStatus.RESERVED, UnitStatus.AVAILABLE,
                                  clear_reservation=True)
            events_repo.add_for_units(conn, reserved, EventType.RELEASED, actor_id=actor.id, request_id=request_id,
                                      note="request cancelled")
        requests_repo.set_status(conn, request_id, OPEN, RequestStatus.CANCELLED.value)
        audit.record(conn, "REQUEST_CANCELLED", f"Request {request_id} cancelled", actor_id=actor.id,
                     entity_type="request", entity_id=request_id, before={"status": request["status"]},
                     after={"status": "CANCELLED", "released": len(reserved), "reason": reason})
        for hospital_id in {u["hospital_id"] for u in reserved}:
            stock.refresh_status(conn, hospital_id)
