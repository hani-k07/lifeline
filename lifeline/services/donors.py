from __future__ import annotations

import re
from datetime import date

from lifeline import clock
from lifeline.db.connection import transaction
from lifeline.db.repositories import audit, people
from lifeline.errors import NotFound, ValidationError
from lifeline.services.common import Actor, authorize_hospital, check_group, require_hospital

_DIGITS = re.compile(r"\D")


def normalize_cnic(raw: str) -> str | None:
    """'3520212345671' or '35202-1234567-1' -> '35202-1234567-1'; blank -> None."""
    if not raw or not raw.strip():
        return None
    digits = _DIGITS.sub("", raw)
    if len(digits) != 13:
        raise ValidationError("CNIC must have 13 digits (e.g. 35202-1234567-1).")
    return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"


def register_donor(actor: Actor, hospital_id: int, name: str, blood_group: str, *, cnic: str = "", phone: str = "",
                   age: int | None = None, last_donated: date | None = None, notes: str = "") -> int:
    authorize_hospital(actor, hospital_id)
    if not name.strip():
        raise ValidationError("Donor name is required.")
    check_group(blood_group)
    if age is not None and not 16 <= age <= 100:
        raise ValidationError("Age must be between 16 and 100.")
    if last_donated is not None and last_donated > clock.today():
        raise ValidationError("Last donation date cannot be in the future.")
    normalized = normalize_cnic(cnic)
    with transaction() as conn:
        require_hospital(conn, hospital_id)
        if normalized and people.donor_by_cnic(conn, normalized):
            raise ValidationError("A donor with this CNIC is already registered.")
        donor_id = people.donor_insert(
            conn, name=name.strip(), cnic=normalized, phone=phone.strip() or None, blood_group=blood_group,
            hospital_id=hospital_id, age=age, last_donated=last_donated.isoformat() if last_donated else None,
            eligible=True, notes=notes.strip() or None)
        audit.record(conn, "DONOR_REGISTERED", f"Donor registered ({blood_group})", actor_id=actor.id,
                     entity_type="donor", entity_id=donor_id, after={"hospital_id": hospital_id, "blood_group": blood_group})
    return donor_id


def record_screening(actor: Actor, donor_id: int, hospital_id: int, *, hiv: bool = False, hepatitis_b: bool = False,
                     hepatitis_c: bool = False, syphilis: bool = False, malaria: bool = False,
                     decision: str | None = None, risk_score: int | None = None) -> int:
    """Store a screening result. A serology positive or a DEFER/BLOCK decision marks the donor ineligible."""
    authorize_hospital(actor, hospital_id)
    if decision not in (None, "SAFE", "DEFER", "BLOCK"):
        raise ValidationError("Unknown screening decision.")
    if risk_score is not None and not 0 <= risk_score <= 100:
        raise ValidationError("Risk score must be between 0 and 100.")
    with transaction() as conn:
        donor = people.donor_get(conn, donor_id)
        if donor is None:
            raise NotFound(f"Donor {donor_id} does not exist.")
        screening_id = people.screening_insert(
            conn, donor_id=donor_id, hospital_id=hospital_id, hiv=hiv, hepatitis_b=hepatitis_b, hepatitis_c=hepatitis_c,
            syphilis=syphilis, malaria=malaria, decision=decision, risk_score=risk_score, created_by=actor.id)
        positive = any((hiv, hepatitis_b, hepatitis_c, syphilis, malaria))
        eligible = not positive and decision in (None, "SAFE")
        people.donor_set_eligible(conn, donor_id, eligible)
        audit.record(conn, "SCREENING", f"Screening recorded ({decision or 'no decision'})", actor_id=actor.id,
                     entity_type="screening", entity_id=screening_id,
                     before={"eligible": bool(donor["eligible"])},
                     after={"eligible": eligible, "decision": decision, "serology_positive": positive, "donor_id": donor_id})
    return screening_id
