from __future__ import annotations

from lifeline import clock
from lifeline.constants import EventType, UnitStatus
from lifeline.db.connection import transaction
from lifeline.db.repositories import audit, people
from lifeline.db.repositories import events as events_repo
from lifeline.db.repositories import units as units_repo
from lifeline.engine.compatibility import can_donate
from lifeline.errors import IncompatibleBlood, InsufficientStock, ValidationError
from lifeline.services import stock
from lifeline.services.common import Actor, authorize_hospital, check_count, check_group, require_hospital

MAX_UNITS_PER_TRANSFUSION = 20


def record_transfusion(actor: Actor, hospital_id: int, patient_name: str, patient_blood_group: str,
                       unit_blood_group: str, units: int, performed_by: str = "", notes: str = "") -> int:
    """Transfuse `units` units of `unit_blood_group` into a patient. Checks ABO/Rh compatibility BEFORE touching
    anything, takes the units First-Expired-First-Out, and links each unit to the transfusion. All or nothing."""
    authorize_hospital(actor, hospital_id)
    if not patient_name.strip():
        raise ValidationError("Patient name is required.")
    check_group(patient_blood_group)
    check_group(unit_blood_group)
    check_count(units, maximum=MAX_UNITS_PER_TRANSFUSION)
    if not can_donate(unit_blood_group, patient_blood_group):
        raise IncompatibleBlood(unit_blood_group, patient_blood_group)
    today = clock.today().isoformat()
    with transaction() as conn:
        require_hospital(conn, hospital_id)
        picked = units_repo.pick_fefo(conn, hospital_id, unit_blood_group, units, today)
        if len(picked) < units:
            raise InsufficientStock(unit_blood_group, units, len(picked))
        transfusion_id = people.transfusion_insert(
            conn, hospital_id=hospital_id, patient_name=patient_name.strip(), patient_blood_group=patient_blood_group,
            blood_group=unit_blood_group, units=units, performed_by=performed_by.strip() or None,
            notes=notes.strip() or None, created_by=actor.id)
        ids = [u["id"] for u in picked]
        units_repo.set_status(conn, ids, UnitStatus.AVAILABLE, UnitStatus.TRANSFUSED, transfusion_id=transfusion_id)
        events_repo.add_for_units(conn, picked, EventType.TRANSFUSED, actor_id=actor.id, note=f"transfusion {transfusion_id}")
        audit.record(conn, "TRANSFUSION", f"{units} unit(s) of {unit_blood_group} transfused", actor_id=actor.id,
                     entity_type="transfusion", entity_id=transfusion_id,
                     after={"patient_group": patient_blood_group, "unit_group": unit_blood_group,
                            "unit_codes": [u["unit_code"] for u in picked]})
        stock.refresh_status(conn, hospital_id)
    return transfusion_id
