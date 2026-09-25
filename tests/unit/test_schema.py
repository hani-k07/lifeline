"""DB-level guarantees, checked against both a fresh database and one migrated from v1."""
import itertools
import shutil
import sqlite3

import pytest

from lifeline.constants import (
    ALLOWED_TRANSITIONS,
    BLOOD_GROUPS,
    ContractStatus,
    EventType,
    ExchangeStatus,
    RequestStatus,
    UnitStatus,
    Urgency,
)
from lifeline.db import migrate
from lifeline.db.schema import create_schema
from tests.legacy_db import make_v1

NOW = "2026-09-25T10:00:00+05:00"


@pytest.fixture(scope="module")
def templates(tmp_path_factory):
    """Build each database once; tests work on cheap file copies."""
    root = tmp_path_factory.mktemp("templates")
    fresh = sqlite3.connect(root / "fresh.db")
    create_schema(fresh)
    fresh.close()
    migrated = sqlite3.connect(make_v1(root / "migrated.db", messy=False))
    migrate.apply_migrations(migrated)
    migrated.execute("DELETE FROM blood_units")                    # start from a known-empty ledger
    migrated.execute("DELETE FROM inventory_events")
    migrated.commit()
    migrated.close()
    return root


@pytest.fixture(params=["fresh", "migrated"])
def db(request, templates, tmp_path):
    shutil.copy(templates / f"{request.param}.db", tmp_path / "t.db")
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("INSERT OR IGNORE INTO hospitals (id, name, city) VALUES (1, 'Mayo', 'Lahore'), (2, 'Services', 'Lahore')")
    conn.execute("INSERT INTO blood_requests (id, requesting_hospital_id, blood_group, units_needed, created_at)"
                 " VALUES (900, 1, 'A+', 1, ?)", (NOW,))
    conn.commit()
    yield conn
    conn.close()


def add_unit(db, status="available", group="A+", collected="2026-09-01", expiry="2026-10-20", code=None, **extra):
    cols = {"unit_code": code or f"T{db.execute('SELECT COALESCE(MAX(id),0)+1 FROM blood_units').fetchone()[0]}",
            "hospital_id": 1, "blood_group": group, "collected_at": collected, "expiry_date": expiry,
            "status": status, "status_changed_at": NOW, "created_at": NOW, **extra}
    if status == "reserved" and "request_id" not in extra:
        cols["request_id"] = 900
    db.execute(f"INSERT INTO blood_units ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", list(cols.values()))
    return db.execute("SELECT MAX(id) FROM blood_units").fetchone()[0]


def rejected(db, sql, *args):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql, args)


# ------------------------------------------------------------------ state machine

@pytest.mark.parametrize(("old", "new"), list(itertools.product(UnitStatus, UnitStatus)))
def test_trigger_agrees_with_python_transition_table(db, old, new):
    unit = add_unit(db, old.value)
    sql, args = "UPDATE blood_units SET status = ? WHERE id = ?", [new.value, unit]
    if new is UnitStatus.RESERVED:
        sql, args = "UPDATE blood_units SET status = ?, request_id = 900 WHERE id = ?", [new.value, unit]
    if new is old or new in ALLOWED_TRANSITIONS[old]:
        db.execute(sql, args)
        assert db.execute("SELECT status FROM blood_units WHERE id = ?", (unit,)).fetchone()[0] == new.value
    else:
        with pytest.raises(sqlite3.IntegrityError, match="invalid blood unit status transition"):
            db.execute(sql, args)


def test_a_unit_cannot_be_issued_twice(db):
    unit = add_unit(db)
    first = db.execute("UPDATE blood_units SET status='issued' WHERE id=? AND status='available'", (unit,)).rowcount
    second = db.execute("UPDATE blood_units SET status='issued' WHERE id=? AND status='available'", (unit,)).rowcount
    assert (first, second) == (1, 0)                                # the guarded UPDATE matches once
    rejected(db, "UPDATE blood_units SET status='available' WHERE id=?", unit)   # and cannot be rolled back to stock
    rejected(db, "UPDATE blood_units SET status='reserved', request_id=900 WHERE id=?", unit)


def test_what_a_unit_is_cannot_be_edited(db):
    unit = add_unit(db)
    rejected(db, "UPDATE blood_units SET blood_group='O-' WHERE id=?", unit)
    rejected(db, "UPDATE blood_units SET expiry_date='2030-01-01' WHERE id=?", unit)
    db.execute("UPDATE blood_units SET hospital_id=2 WHERE id=?", (unit,))     # custody may change


# ------------------------------------------------------------------ CHECK constraints

def test_blood_group_enum_everywhere(db):
    for bad in ("ZZ", "a+", "", "AB"):
        rejected(db, "INSERT INTO donors (name, blood_group) VALUES ('d', ?)", bad)
        rejected(db, "INSERT INTO blood_requests (requesting_hospital_id, blood_group, units_needed, created_at)"
                     " VALUES (1, ?, 1, ?)", bad, NOW)
        with pytest.raises(sqlite3.IntegrityError):
            add_unit(db, group=bad)
    for good in BLOOD_GROUPS:
        add_unit(db, group=good)


def test_positive_units_and_distinct_hospitals(db):
    rejected(db, "INSERT INTO blood_requests (requesting_hospital_id, blood_group, units_needed, created_at)"
                 " VALUES (1, 'A+', 0, ?)", NOW)
    rejected(db, "INSERT INTO transfusions (hospital_id, blood_group, units, transfused_at) VALUES (1, 'A+', -1, ?)", NOW)
    rejected(db, "INSERT INTO exchanges (from_hospital_id, to_hospital_id, blood_group, units, created_at)"
                 " VALUES (1, 2, 'A+', 0, ?)", NOW)
    rejected(db, "INSERT INTO exchanges (from_hospital_id, to_hospital_id, blood_group, units, created_at)"
                 " VALUES (1, 1, 'A+', 1, ?)", NOW)
    rejected(db, "INSERT INTO contracts (ticket_id, lending_hospital_id, borrowing_hospital_id, blood_group, units,"
                 " created_at, return_deadline) VALUES ('T', 1, 1, 'A+', 1, ?, ?)", NOW, NOW)
    rejected(db, "INSERT INTO contracts (ticket_id, lending_hospital_id, borrowing_hospital_id, blood_group, units,"
                 " created_at, return_deadline) VALUES ('T', 1, 2, 'A+', 0, ?, ?)", NOW, NOW)


def test_unit_dates_and_reservation_rules(db):
    with pytest.raises(sqlite3.IntegrityError):
        add_unit(db, collected="2026-10-01", expiry="2026-09-01")     # expires before it was collected
    with pytest.raises(sqlite3.IntegrityError):
        add_unit(db, "reserved", request_id=None)                     # reserved for nobody
    with pytest.raises(sqlite3.IntegrityError):
        add_unit(db, code="DUP"), add_unit(db, code="DUP")            # unit codes are unique


def test_enum_columns_accept_every_python_value_and_nothing_else(db):
    for s in RequestStatus:
        db.execute("INSERT INTO blood_requests (requesting_hospital_id, blood_group, units_needed, status, created_at)"
                   " VALUES (1,'A+',1,?,?)", (s.value, NOW))
    for u in Urgency:
        db.execute("INSERT INTO blood_requests (requesting_hospital_id, blood_group, units_needed, urgency, created_at)"
                   " VALUES (1,'A+',1,?,?)", (u.value, NOW))
    for s in ExchangeStatus:
        db.execute("INSERT INTO exchanges (from_hospital_id, to_hospital_id, blood_group, units, status, created_at)"
                   " VALUES (1,2,'A+',1,?,?)", (s.value, NOW))
    for i, s in enumerate(ContractStatus):
        db.execute("INSERT INTO contracts (ticket_id, lending_hospital_id, borrowing_hospital_id, blood_group, units,"
                   " created_at, return_deadline, status) VALUES (?,1,2,'A+',1,?,?,?)", (f"T{i}", NOW, NOW, s.value))
    for e in EventType:
        db.execute("INSERT INTO inventory_events (at, hospital_id, blood_group, event_type) VALUES (?,1,'A+',?)",
                   (NOW, e.value))
    rejected(db, "INSERT INTO blood_requests (requesting_hospital_id, blood_group, units_needed, status, created_at)"
                 " VALUES (1,'A+',1,'DONE',?)", NOW)
    rejected(db, "INSERT INTO inventory_events (at, hospital_id, blood_group, event_type) VALUES (?,1,'A+','lost')", NOW)
    rejected(db, "INSERT INTO hospitals (id, name, city, stock_status) VALUES (9,'X','L','great')")
    rejected(db, "INSERT INTO hospitals (id, name, city, latitude) VALUES (9,'X','L',123)")
    rejected(db, "INSERT INTO donors (name, blood_group, eligible) VALUES ('d','A+',2)")


def test_unique_hospital_names_and_donor_cnic(db):
    rejected(db, "INSERT INTO hospitals (id, name, city) VALUES (9, 'Mayo', 'Lahore')")
    db.execute("INSERT INTO donors (name, cnic, blood_group) VALUES ('a', '35202-2222222-2', 'A+')")
    rejected(db, "INSERT INTO donors (name, cnic, blood_group) VALUES ('b', '35202-2222222-2', 'A+')")
    db.execute("INSERT INTO donors (name, cnic, blood_group) VALUES ('c', NULL, 'A+')")
    db.execute("INSERT INTO donors (name, cnic, blood_group) VALUES ('d', NULL, 'A+')")     # many donors without a CNIC


def test_foreign_keys_are_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        add_unit(db, hospital_id=999)
    rejected(db, "INSERT INTO blood_requests (requesting_hospital_id, blood_group, units_needed, created_at)"
                 " VALUES (999,'A+',1,?)", NOW)


# ------------------------------------------------------------------ audit + indexes

def test_audit_log_is_append_only_but_writable(db):
    db.execute("INSERT INTO audit_logs (action_type, description, timestamp, entity_type, entity_id, before_json, after_json)"
               " VALUES ('X', 'd', ?, 'unit', '1', '{}', '{}')", (NOW,))
    rejected(db, "UPDATE audit_logs SET description = 'edited'")
    rejected(db, "DELETE FROM audit_logs")


def test_required_indexes_exist(db):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"ix_units_stock", "ix_units_expiry", "ix_units_status", "ix_requests_status", "ix_units_request",
            "ix_events_hospital_at", "ix_contracts_status_deadline", "ix_audit_timestamp"} <= names


def test_stock_queries_use_the_index(db):
    plan = " ".join(r[3] for r in db.execute(
        "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM blood_units WHERE hospital_id=1 AND blood_group='A+' AND status='available'"))
    assert "ix_units_stock" in plan
