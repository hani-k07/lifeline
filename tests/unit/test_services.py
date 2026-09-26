import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pytest

from lifeline import clock
from lifeline.config import get_settings
from lifeline.db.connection import connect
from lifeline.db.schema import create_schema
from lifeline.errors import (
    IncompatibleBlood,
    InsufficientStock,
    InvalidTransition,
    NotAuthorized,
    NotFound,
    ValidationError,
)
from lifeline.services import contracts, donors, emergency, exchanges, housekeeping, inventory, stock, transfusion
from lifeline.services.common import SYSTEM

FIXED_NOW = datetime(2026, 9, 25, 12, 0, 0, tzinfo=clock.PKT)
TODAY = FIXED_NOW.date()


@dataclass(frozen=True)
class Who:
    id: int | None
    hospital_id: int | None
    is_super: bool = False


ADMIN = Who(1, None, True)
MAYO = Who(2, 1)          # staff at hospital 1
SERVICES = Who(3, 2)      # staff at hospital 2


@pytest.fixture(autouse=True)
def world(monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: FIXED_NOW)
    conn = sqlite3.connect(get_settings().db_path)
    create_schema(conn)
    conn.executemany("INSERT INTO hospitals (id, name, city) VALUES (?,?,'Lahore')",
                     [(1, "Mayo"), (2, "Services"), (3, "Jinnah")])
    for i, hospital in ((1, None), (2, 1), (3, 2)):
        conn.execute("INSERT INTO users (id, email, password_hash, role, name, created_at, hospital_id) VALUES (?,?,?,?,?,?,?)",
                     (i, f"u{i}@x.pk", "h", "super_admin" if hospital is None else "staff", f"U{i}", "t", hospital))
    conn.commit()
    conn.close()


def q(sql, *args):
    conn = connect()
    try:
        return [tuple(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()


def stock_of(hospital, group, status="available"):
    return q("SELECT COUNT(*) FROM blood_units WHERE hospital_id=? AND blood_group=? AND status=?", hospital, group, status)[0][0]


def receive(who, hospital, group, n, days=20):
    return inventory.receive_units(who, hospital, group, n, TODAY + timedelta(days=days))


def actions():
    return [r[0] for r in q("SELECT action_type FROM audit_logs ORDER BY id")]


# ------------------------------------------------------------------ receiving

def test_receive_creates_units_events_audit_and_status():
    ids = receive(MAYO, 1, "A+", 5)
    assert len(ids) == 5 and stock_of(1, "A+") == 5
    assert q("SELECT DISTINCT event_type FROM inventory_events") == [("received",)]
    audit = q("SELECT action_type, entity_type, entity_id, user_id, timestamp, after_json FROM audit_logs")[0]
    assert audit[:4] == ("STOCK_RECEIVED", "hospital_stock", "1", 2)
    assert audit[4] == "2026-09-25T12:00:00+05:00"            # PKT with explicit offset
    assert '"count": 5' in audit[5]
    assert q("SELECT stock_status FROM hospitals WHERE id=1") == [("critical",)]     # 5 units in total is very low


@pytest.mark.parametrize(
    ("kwargs", "fragment"),
    [
        (dict(count=0), "at least 1"),
        (dict(count=501), "cannot exceed"),
        (dict(blood_group="Z+"), "Unknown blood group"),
        (dict(days=0), "already expired"),
        (dict(days=-3), "already expired"),
        (dict(days=90), "60 days"),
        (dict(collected=TODAY + timedelta(days=1)), "future"),
    ],
)
def test_receive_validation_writes_nothing(kwargs, fragment):
    args = dict(count=1, blood_group="A+", days=20, collected=None)
    args.update(kwargs)
    with pytest.raises(ValidationError, match=fragment):
        inventory.receive_units(MAYO, 1, args["blood_group"], args["count"], TODAY + timedelta(days=args["days"]),
                                collected_at=args["collected"])
    assert q("SELECT COUNT(*) FROM blood_units") == [(0,)] and actions() == []


def test_staff_cannot_touch_another_hospital():
    with pytest.raises(NotAuthorized):
        receive(SERVICES, 1, "A+", 1)
    with pytest.raises(NotAuthorized):
        inventory.issue_units(SERVICES, 1, "A+", 1)
    receive(ADMIN, 1, "A+", 1)                                  # a super admin may
    with pytest.raises(NotFound):
        receive(ADMIN, 99, "A+", 1)


# ------------------------------------------------------------------ issuing / FEFO

def test_issue_takes_earliest_expiry_first_and_is_audited():
    late = receive(MAYO, 1, "O+", 2, days=30)
    early = receive(MAYO, 1, "O+", 2, days=5)
    codes = inventory.issue_units(MAYO, 1, "O+", 3, "surgery")
    issued = [r[0] for r in q("SELECT id FROM blood_units WHERE status='issued' ORDER BY expiry_date, id")]
    assert issued == early + late[:1]                          # both early units, then the earliest of the late batch
    assert len(codes) == 3
    entry = q("SELECT action_type, before_json, after_json FROM audit_logs WHERE action_type='STOCK_ISSUED'")[0]
    assert '"available": 4' in entry[1] and "surgery" in entry[2]


def test_insufficient_stock_is_all_or_nothing():
    receive(MAYO, 1, "A+", 2)
    before_audit = len(actions())
    with pytest.raises(InsufficientStock) as info:
        inventory.issue_units(MAYO, 1, "A+", 3)
    assert (info.value.available, info.value.wanted) == (2, 3)
    assert stock_of(1, "A+") == 2 and stock_of(1, "A+", "issued") == 0 and len(actions()) == before_audit


def test_expired_but_unswept_units_are_never_issued():
    conn = connect()
    conn.execute("INSERT INTO blood_units (unit_code, hospital_id, blood_group, collected_at, expiry_date, status,"
                 " status_changed_at, created_at) VALUES ('OLD',1,'A+','2026-07-01','2026-09-24','available','t','t')")
    conn.commit()
    conn.close()
    with pytest.raises(InsufficientStock):
        inventory.issue_units(MAYO, 1, "A+", 1)                 # available on paper, but past its date


def test_discard_requires_reason_and_a_live_unit():
    (unit,) = receive(MAYO, 1, "A+", 1)
    with pytest.raises(ValidationError):
        inventory.discard_unit(MAYO, unit, "  ")
    inventory.discard_unit(MAYO, unit, "cold chain broken")
    with pytest.raises(InvalidTransition):
        inventory.discard_unit(MAYO, unit, "again")
    assert stock_of(1, "A+", "discarded") == 1


# ------------------------------------------------------------------ double issue

def test_concurrent_issuers_cannot_both_get_the_last_unit():
    receive(MAYO, 1, "B+", 1)
    results: list[str] = []

    def worker():
        try:
            inventory.issue_units(MAYO, 1, "B+", 1)
            results.append("ok")
        except InsufficientStock:
            results.append("none")

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["none"] * 5 + ["ok"]
    assert stock_of(1, "B+", "issued") == 1


# ------------------------------------------------------------------ transfusion

def test_incompatible_transfusion_is_refused_before_any_write():
    receive(MAYO, 1, "A+", 2)
    with pytest.raises(IncompatibleBlood):
        transfusion.record_transfusion(MAYO, 1, "Patient", "O-", "A+", 1)
    assert stock_of(1, "A+") == 2 and q("SELECT COUNT(*) FROM transfusions") == [(0,)]
    assert "TRANSFUSION" not in actions()


def test_compatible_transfusion_links_units_and_never_stores_the_name_in_audit():
    receive(MAYO, 1, "O-", 3)
    tid = transfusion.record_transfusion(MAYO, 1, "Ali Hassan", "A+", "O-", 2, "Dr Z", "post-op")
    assert q("SELECT COUNT(*) FROM blood_units WHERE transfusion_id=? AND status='transfused'", tid) == [(2,)]
    assert q("SELECT patient_blood_group, blood_group, units FROM transfusions") == [("A+", "O-", 2)]
    assert q("SELECT COUNT(*) FROM inventory_events WHERE event_type='transfused'") == [(2,)]
    audit_text = " ".join(str(r) for r in q("SELECT description, before_json, after_json FROM audit_logs"))
    assert "Ali Hassan" not in audit_text


def test_transfusion_needs_stock_and_a_patient():
    with pytest.raises(InsufficientStock):
        transfusion.record_transfusion(MAYO, 1, "P", "A+", "A+", 1)
    with pytest.raises(ValidationError):
        transfusion.record_transfusion(MAYO, 1, " ", "A+", "A+", 1)


# ------------------------------------------------------------------ emergency requests

def test_request_reserve_fulfil_flow():
    receive(SERVICES, 2, "O-", 4)
    rid = emergency.create_request(MAYO, 1, "A+", 3, "CRITICAL", "Ali", "trauma")
    codes = emergency.reserve_units(MAYO, rid, 2, "O-", 2)                  # O- is compatible with an A+ patient
    assert len(codes) == 2 and stock_of(2, "O-", "reserved") == 2 and stock_of(2, "O-") == 2
    assert q("SELECT status FROM blood_requests") == [("RESERVED",)]
    with pytest.raises(ValidationError, match="reserve the rest"):
        emergency.fulfil_request(MAYO, rid)
    with pytest.raises(ValidationError, match="already reserved"):
        emergency.reserve_units(MAYO, rid, 2, "O-", 2)                       # 2 + 2 > 3
    emergency.reserve_units(MAYO, rid, 2, "O-", 1)
    emergency.fulfil_request(MAYO, rid)
    assert stock_of(2, "O-", "issued") == 3 and q("SELECT status FROM blood_requests") == [("RESOLVED",)]
    assert {"EMERGENCY_REQUEST", "REQUEST_RESERVED", "REQUEST_FULFILLED"} <= set(actions())


def test_reserving_incompatible_units_is_refused():
    receive(SERVICES, 2, "A+", 2)
    rid = emergency.create_request(MAYO, 1, "O-", 1, "URGENT", "P")
    with pytest.raises(IncompatibleBlood):
        emergency.reserve_units(MAYO, rid, 2, "A+", 1)


def test_cancel_returns_reserved_units_to_stock():
    receive(SERVICES, 2, "O+", 3)
    rid = emergency.create_request(MAYO, 1, "O+", 2, "ROUTINE", "P")
    emergency.reserve_units(MAYO, rid, 2, "O+", 2)
    emergency.cancel_request(MAYO, rid, "not needed")
    assert stock_of(2, "O+") == 3 and stock_of(2, "O+", "reserved") == 0
    assert q("SELECT status FROM blood_requests") == [("CANCELLED",)]
    with pytest.raises(ValidationError):
        emergency.cancel_request(MAYO, rid)
    assert q("SELECT COUNT(*) FROM inventory_events WHERE event_type='released'") == [(2,)]


def test_only_the_requesting_hospital_drives_its_request():
    rid = emergency.create_request(MAYO, 1, "A+", 1, "ROUTINE", "P")
    with pytest.raises(NotAuthorized):
        emergency.cancel_request(SERVICES, rid)
    with pytest.raises(NotFound):
        emergency.cancel_request(ADMIN, 999)


# ------------------------------------------------------------------ exchanges

def test_exchange_request_accept_complete_moves_units():
    receive(SERVICES, 2, "B+", 5)
    ex = exchanges.request_exchange(MAYO, supplier_id=2, requester_id=1, blood_group="B+", units=3)
    with pytest.raises(NotAuthorized):
        exchanges.respond_exchange(MAYO, ex, True)                           # only the supplier decides
    exchanges.respond_exchange(SERVICES, ex, True)
    assert stock_of(2, "B+", "reserved") == 3 and stock_of(2, "B+") == 2
    exchanges.complete_exchange(MAYO, ex)
    assert stock_of(1, "B+") == 3 and stock_of(2, "B+") == 2 and stock_of(2, "B+", "reserved") == 0
    assert q("SELECT status FROM exchanges") == [("COMPLETED",)]
    assert q("SELECT hospital_id, event_type FROM inventory_events WHERE event_type LIKE 'transferred_%' "
             "GROUP BY 1, 2 ORDER BY 1, 2") == [(1, "transferred_in"), (2, "transferred_out")]


def test_exchange_rules():
    with pytest.raises(ValidationError):
        exchanges.request_exchange(MAYO, 1, 1, "A+", 1)
    ex = exchanges.request_exchange(MAYO, 2, 1, "A+", 2)
    with pytest.raises(InsufficientStock):
        exchanges.respond_exchange(SERVICES, ex, True)                       # supplier has none
    exchanges.respond_exchange(SERVICES, ex, False)
    assert q("SELECT status FROM exchanges") == [("REJECTED",)]
    with pytest.raises(ValidationError):
        exchanges.complete_exchange(MAYO, ex)


def test_cancelled_exchange_releases_units():
    receive(SERVICES, 2, "A-", 2)
    ex = exchanges.request_exchange(MAYO, 2, 1, "A-", 2)
    exchanges.respond_exchange(SERVICES, ex, True)
    exchanges.cancel_exchange(MAYO, ex)
    assert stock_of(2, "A-") == 2 and q("SELECT status FROM exchanges") == [("CANCELLED",)]


# ------------------------------------------------------------------ loans + housekeeping

def test_loan_moves_units_and_return_moves_them_back():
    receive(SERVICES, 2, "O+", 4)
    cid = contracts.create_loan(SERVICES, 2, 1, "O+", 3, FIXED_NOW + timedelta(days=2))
    assert stock_of(1, "O+") == 3 and stock_of(2, "O+") == 1
    ticket = q("SELECT ticket_id, status FROM contracts")[0]
    assert ticket == (f"LF-2026-{cid:04d}", "ACTIVE")
    contracts.return_loan(MAYO, cid)
    assert stock_of(1, "O+") == 0 and stock_of(2, "O+") == 4 and q("SELECT status FROM contracts") == [("RETURNED",)]


def test_loan_validation_and_borrower_without_stock_cannot_return():
    receive(SERVICES, 2, "O+", 1)
    with pytest.raises(ValidationError):
        contracts.create_loan(SERVICES, 2, 2, "O+", 1, FIXED_NOW + timedelta(days=1))
    with pytest.raises(ValidationError, match="future"):
        contracts.create_loan(SERVICES, 2, 1, "O+", 1, FIXED_NOW - timedelta(hours=1))
    with pytest.raises(ValidationError, match="30 days"):
        contracts.create_loan(SERVICES, 2, 1, "O+", 1, FIXED_NOW + timedelta(days=45))
    with pytest.raises(InsufficientStock):
        contracts.create_loan(SERVICES, 2, 1, "O+", 5, FIXED_NOW + timedelta(days=1))
    cid = contracts.create_loan(SERVICES, 2, 1, "O+", 1, FIXED_NOW + timedelta(days=1))
    inventory.issue_units(MAYO, 1, "O+", 1)                                  # borrower used it
    with pytest.raises(InsufficientStock):
        contracts.return_loan(MAYO, cid)
    with pytest.raises(NotAuthorized):
        contracts.return_loan(Who(9, 3), cid)


def test_housekeeping_expires_units_breaches_loans_and_is_idempotent(monkeypatch):
    receive(SERVICES, 2, "O+", 3, days=2)
    receive(SERVICES, 2, "A+", 1, days=40)
    cid = contracts.create_loan(SERVICES, 2, 1, "O+", 1, FIXED_NOW + timedelta(hours=6))
    first = housekeeping.run()
    assert (first.expired_units, first.breached_contracts) == (0, 0)

    later = FIXED_NOW + timedelta(days=3)
    monkeypatch.setattr(clock, "now", lambda: later)
    result = housekeeping.run()
    assert (result.expired_units, result.breached_contracts) == (3, 1)
    assert stock_of(1, "O+", "expired") + stock_of(2, "O+", "expired") == 3
    assert q("SELECT status FROM contracts WHERE id=?", cid) == [("BREACHED",)]
    assert {"UNITS_EXPIRED", "CONTRACT_BREACHED"} <= set(actions())
    again = housekeeping.run()
    assert (again.expired_units, again.breached_contracts) == (0, 0)


def test_a_reserved_unit_that_expires_frees_the_request_to_reserve_more(monkeypatch):
    receive(SERVICES, 2, "O-", 2, days=1)
    receive(SERVICES, 2, "O-", 2, days=30)
    rid = emergency.create_request(MAYO, 1, "O-", 1, "URGENT", "P")
    emergency.reserve_units(MAYO, rid, 2, "O-", 1)                           # takes a day-1 unit
    monkeypatch.setattr(clock, "now", lambda: FIXED_NOW + timedelta(days=2))
    assert housekeeping.run().expired_units == 2                            # 1 available + the reserved one
    with pytest.raises(ValidationError, match="reserve the rest"):
        emergency.fulfil_request(MAYO, rid)
    emergency.reserve_units(MAYO, rid, 2, "O-", 1)                           # the request can draw a fresh unit
    emergency.fulfil_request(MAYO, rid)


# ------------------------------------------------------------------ donors, screening, stock status

def test_donor_registration_rules():
    did = donors.register_donor(MAYO, 1, "Ali", "O+", cnic="3520212345671", age=30)
    assert q("SELECT cnic, eligible FROM donors WHERE id=?", did) == [("35202-1234567-1", 1)]
    with pytest.raises(ValidationError, match="already registered"):
        donors.register_donor(MAYO, 1, "Twin", "O+", cnic="35202-1234567-1")
    with pytest.raises(ValidationError, match="13 digits"):
        donors.register_donor(MAYO, 1, "X", "O+", cnic="1234")
    with pytest.raises(ValidationError):
        donors.register_donor(MAYO, 1, "X", "O+", last_donated=date(2999, 1, 1))
    assert "35202" not in " ".join(str(r) for r in q("SELECT description, after_json FROM audit_logs"))


def test_screening_updates_eligibility_from_serology_and_decision():
    did = donors.register_donor(MAYO, 1, "Ali", "O+")
    donors.record_screening(MAYO, did, 1, decision="DEFER", risk_score=55)
    assert q("SELECT eligible FROM donors") == [(0,)]
    donors.record_screening(MAYO, did, 1, decision="SAFE", risk_score=90)
    assert q("SELECT eligible FROM donors") == [(1,)]
    donors.record_screening(MAYO, did, 1, hiv=True, decision="SAFE")         # serology overrides a SAFE decision
    assert q("SELECT eligible FROM donors") == [(0,)]
    assert q("SELECT result FROM screening_tests ORDER BY id DESC LIMIT 1") == [("FAIL",)]


ALL = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")


@pytest.mark.parametrize(
    ("counts", "expected"),
    [
        ({}, "critical"),
        ({g: 10 for g in ALL}, "ok"),
        ({"A+": 40, "B+": 40}, "critical"),                                   # O+ and O- are empty
        ({"A+": 5, "B+": 5}, "critical"),                                     # 10 units in total
        ({g: 7 for g in ALL}, "low"),                                         # 56 units, key groups below the low level
        ({**{g: 12 for g in ALL}, "AB-": 0}, "low"),                          # only a rare group is out
        ({**{g: 12 for g in ALL}, "O-": 2}, "critical"),                      # universal donor almost gone
        ({**{g: 12 for g in ALL}, "B+": 6}, "low"),                           # a key group is low, none critical
    ],
)
def test_hospital_status_rule(counts, expected):
    assert stock.hospital_status(counts) == expected


def test_system_actor_can_act_anywhere():
    receive(SYSTEM, 3, "A+", 1)
    assert stock_of(3, "A+") == 1


# ------------------------------------------------------------------ atomic emergency confirm (create + reserve + audit)

def test_create_and_reserve_is_one_atomic_step():
    receive(SERVICES, 2, "O-", 3)
    receive(ADMIN, 3, "A+", 2)
    request_id, codes = emergency.create_and_reserve(MAYO, 1, "A+", 4, "CRITICAL", "Patient", "trauma",
                                                     [(3, "A+", 2), (2, "O-", 2)])
    assert len(codes) == 4 and q("SELECT status FROM blood_requests WHERE id=?", request_id) == [("RESERVED",)]
    assert stock_of(3, "A+", "reserved") == 2 and stock_of(2, "O-", "reserved") == 2
    logged = actions()
    assert logged.count("REQUEST_RESERVED") == 2 and "EMERGENCY_REQUEST" in logged
    emergency.fulfil_request(MAYO, request_id)                                   # and it can be dispatched straight away
    assert q("SELECT status FROM blood_requests WHERE id=?", request_id) == [("RESOLVED",)]


@pytest.mark.parametrize(
    ("units", "sources", "error"),
    [
        (5, [(2, "O-", 5)], InsufficientStock),            # only 3 O- exist: stock changed since the search
        (2, [(2, "A+", 2)], InsufficientStock),            # the hospital holds none of that group
        (2, [(2, "B+", 2)], IncompatibleBlood),            # B+ blood is not compatible with an A+ patient
        (2, [(2, "O-", 1)], ValidationError),              # does not cover the 2 units needed
        (2, [(2, "O-", 3)], ValidationError),              # covers more than needed
    ],
)
def test_create_and_reserve_writes_nothing_when_any_step_fails(units, sources, error):
    receive(SERVICES, 2, "O-", 3)
    before = (q("SELECT COUNT(*) FROM blood_requests")[0][0], stock_of(2, "O-"), len(actions()))
    with pytest.raises(error):
        emergency.create_and_reserve(MAYO, 1, "A+", units, "URGENT", "P", "", sources)
    assert (q("SELECT COUNT(*) FROM blood_requests")[0][0], stock_of(2, "O-"), len(actions())) == before


def test_create_and_reserve_second_source_failure_rolls_back_the_first():
    receive(SERVICES, 2, "O-", 2)                                                   # source 3 has nothing
    with pytest.raises(InsufficientStock):
        emergency.create_and_reserve(MAYO, 1, "A+", 4, "URGENT", "P", "", [(2, "O-", 2), (3, "A+", 2)])
    assert stock_of(2, "O-") == 2 and stock_of(2, "O-", "reserved") == 0 and q("SELECT COUNT(*) FROM blood_requests") == [(0,)]


def test_create_and_reserve_validation_and_authorisation():
    with pytest.raises(NotAuthorized):
        emergency.create_and_reserve(SERVICES, 1, "A+", 1, "URGENT", "P", "", [(2, "O-", 1)])
    with pytest.raises(ValidationError):
        emergency.create_and_reserve(MAYO, 1, "A+", 1, "URGENT", " ", "", [(2, "O-", 1)])
    with pytest.raises(ValidationError):
        emergency.create_and_reserve(MAYO, 1, "A+", 1, "whenever", "P", "", [(2, "O-", 1)])
    with pytest.raises(ValidationError):
        emergency.create_and_reserve(MAYO, 1, "A+", 1, "URGENT", "P", "", [])
