"""Hospital-to-hospital loans: the units move when the loan is made and must come back by the deadline."""
from __future__ import annotations

from datetime import datetime, timedelta

from lifeline import clock
from lifeline.constants import MAX_UNITS_PER_RECEIPT, ContractStatus, EventType
from lifeline.db.connection import transaction
from lifeline.db.repositories import audit
from lifeline.db.repositories import contracts as contracts_repo
from lifeline.db.repositories import events as events_repo
from lifeline.db.repositories import units as units_repo
from lifeline.errors import InsufficientStock, NotFound, ValidationError
from lifeline.services import stock
from lifeline.services.common import Actor, authorize_any, authorize_hospital, check_count, check_group, require_hospital

MAX_LOAN_DAYS = 30
OPEN = (ContractStatus.ACTIVE.value, ContractStatus.BREACHED.value)


def create_loan(actor: Actor, lender_id: int, borrower_id: int, blood_group: str, units: int,
                return_deadline: datetime) -> int:
    """`lender_id` lends units to `borrower_id`, to be returned by `return_deadline` (timezone-aware)."""
    authorize_hospital(actor, lender_id)
    check_group(blood_group)
    check_count(units, maximum=MAX_UNITS_PER_RECEIPT)
    if lender_id == borrower_id:
        raise ValidationError("A hospital cannot lend to itself.")
    now = clock.now()
    if return_deadline.tzinfo is None:
        raise ValidationError("Return deadline needs a timezone.")
    if return_deadline <= now:
        raise ValidationError("Return deadline must be in the future.")
    if return_deadline > now + timedelta(days=MAX_LOAN_DAYS):
        raise ValidationError(f"Loans cannot run longer than {MAX_LOAN_DAYS} days.")
    today = now.date().isoformat()
    with transaction() as conn:
        require_hospital(conn, lender_id)
        require_hospital(conn, borrower_id)
        picked = units_repo.pick_fefo(conn, lender_id, blood_group, units, today)
        if len(picked) < units:
            raise InsufficientStock(blood_group, units, len(picked))
        deadline_pkt = return_deadline.astimezone(clock.PKT).isoformat(timespec="seconds")
        contract_id = contracts_repo.insert(conn, lender_id=lender_id, borrower_id=borrower_id, blood_group=blood_group,
                                            units=units, return_deadline=deadline_pkt, created_by=actor.id)
        units_repo.transfer(conn, [u["id"] for u in picked], borrower_id)
        note = f"loan {contract_id}"
        events_repo.add_for_units(conn, picked, EventType.TRANSFERRED_OUT, actor_id=actor.id, note=note, hospital_id=lender_id)
        events_repo.add_for_units(conn, picked, EventType.TRANSFERRED_IN, actor_id=actor.id, note=note, hospital_id=borrower_id)
        audit.record(conn, "LOAN_CREATED", f"{units}u {blood_group} lent", actor_id=actor.id, entity_type="contract",
                     entity_id=contract_id,
                     after={"lender_id": lender_id, "borrower_id": borrower_id, "units": units, "blood_group": blood_group,
                            "return_deadline": return_deadline.isoformat(timespec="seconds"),
                            "unit_codes": [u["unit_code"] for u in picked]})
        stock.refresh_status(conn, lender_id)
        stock.refresh_status(conn, borrower_id)
    return contract_id


def return_loan(actor: Actor, contract_id: int) -> None:
    """The borrower hands the same number of units of the same group back. Late returns are allowed (and flagged)."""
    today = clock.today().isoformat()
    with transaction() as conn:
        contract = contracts_repo.get(conn, contract_id)
        if contract is None:
            raise NotFound(f"Contract {contract_id} does not exist.")
        authorize_any(actor, contract["lending_hospital_id"], contract["borrowing_hospital_id"])
        if contract["status"] not in OPEN:
            raise ValidationError(f"Contract is already {contract['status'].lower()}.")
        picked = units_repo.pick_fefo(conn, contract["borrowing_hospital_id"], contract["blood_group"], contract["units"], today)
        if len(picked) < contract["units"]:
            raise InsufficientStock(contract["blood_group"], contract["units"], len(picked))
        units_repo.transfer(conn, [u["id"] for u in picked], contract["lending_hospital_id"])
        note = f"loan {contract_id} returned"
        events_repo.add_for_units(conn, picked, EventType.TRANSFERRED_OUT, actor_id=actor.id, note=note,
                                  hospital_id=contract["borrowing_hospital_id"])
        events_repo.add_for_units(conn, picked, EventType.TRANSFERRED_IN, actor_id=actor.id, note=note,
                                  hospital_id=contract["lending_hospital_id"])
        contracts_repo.set_status(conn, contract_id, OPEN, ContractStatus.RETURNED.value)
        late = clock.now_iso() > contract["return_deadline"]
        audit.record(conn, "LOAN_RETURNED", "Loan returned" + (" late" if late else ""), actor_id=actor.id,
                     entity_type="contract", entity_id=contract_id, before={"status": contract["status"]},
                     after={"status": "RETURNED", "late": late, "unit_codes": [u["unit_code"] for u in picked]})
        stock.refresh_status(conn, contract["lending_hospital_id"])
        stock.refresh_status(conn, contract["borrowing_hospital_id"])
