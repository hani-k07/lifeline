-- LIFELINE schema v2: single source of truth for a fresh database.
-- Existing databases reach the same shape through lifeline/db/migrations/ (a test asserts they match).
-- Blood units are individual rows with a status; stock is COUNT(*) of 'available' units.

PRAGMA foreign_keys = ON;

CREATE TABLE hospitals (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    city         TEXT NOT NULL,
    address      TEXT,
    latitude     REAL CHECK (latitude BETWEEN -90 AND 90),
    longitude    REAL CHECK (longitude BETWEEN -180 AND 180),
    phone        TEXT,
    stock_status TEXT NOT NULL DEFAULT 'ok' CHECK (stock_status IN ('ok','low','critical'))
);

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK(role IN ('super_admin','hospital_admin','staff')),
    name          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    hospital_id   INTEGER REFERENCES hospitals(id)
);

CREATE TABLE login_throttle (
    email        TEXT PRIMARY KEY,
    failed_count INTEGER NOT NULL DEFAULT 0,
    locked_until INTEGER NOT NULL DEFAULT 0,
    updated_at   INTEGER NOT NULL
);

CREATE TABLE donors (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    cnic          TEXT,
    phone         TEXT,
    blood_group   TEXT NOT NULL CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    hospital_id   INTEGER REFERENCES hospitals(id),
    age           INTEGER CHECK (age IS NULL OR age BETWEEN 16 AND 100),
    times_donated INTEGER NOT NULL DEFAULT 0 CHECK (times_donated >= 0),
    last_donated  TEXT,
    eligible      INTEGER NOT NULL DEFAULT 1 CHECK (eligible IN (0,1)),
    notes         TEXT
);

CREATE TABLE blood_requests (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    requesting_hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    blood_group            TEXT NOT NULL CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    units_needed           INTEGER NOT NULL CHECK (units_needed > 0),
    urgency                TEXT NOT NULL DEFAULT 'ROUTINE' CHECK (urgency IN ('CRITICAL','URGENT','ROUTINE')),
    status                 TEXT NOT NULL DEFAULT 'PENDING'
                           CHECK (status IN ('PENDING','RESERVED','RESOLVED','CANCELLED')),
    patient_name           TEXT,
    patient_condition      TEXT,
    created_at             TEXT NOT NULL,
    created_by             INTEGER REFERENCES users(id),
    resolved_at            TEXT
);

CREATE TABLE transfusions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id         INTEGER NOT NULL REFERENCES hospitals(id),
    patient_name        TEXT,
    patient_blood_group TEXT CHECK (patient_blood_group IS NULL
                                    OR patient_blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    blood_group         TEXT NOT NULL CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    units               INTEGER NOT NULL CHECK (units > 0),
    transfused_at       TEXT NOT NULL,
    performed_by        TEXT,
    notes               TEXT,
    created_by          INTEGER REFERENCES users(id)
);

CREATE TABLE exchanges (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    from_hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    to_hospital_id   INTEGER NOT NULL REFERENCES hospitals(id),
    blood_group      TEXT NOT NULL CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    units            INTEGER NOT NULL CHECK (units > 0),
    status           TEXT NOT NULL DEFAULT 'PENDING'
                     CHECK (status IN ('PENDING','ACCEPTED','COMPLETED','REJECTED','CANCELLED')),
    created_at       TEXT NOT NULL,
    completed_at     TEXT,
    requested_by     INTEGER REFERENCES users(id),
    decided_by       INTEGER REFERENCES users(id),
    CHECK (from_hospital_id <> to_hospital_id)
);

CREATE TABLE blood_units (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_code         TEXT NOT NULL UNIQUE,
    hospital_id       INTEGER NOT NULL REFERENCES hospitals(id),
    blood_group       TEXT NOT NULL CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    donor_id          INTEGER REFERENCES donors(id),
    collected_at      TEXT NOT NULL,
    expiry_date       TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'available'
                      CHECK (status IN ('available','reserved','issued','transfused','expired','discarded')),
    request_id        INTEGER REFERENCES blood_requests(id),
    exchange_id       INTEGER REFERENCES exchanges(id),
    transfusion_id    INTEGER REFERENCES transfusions(id),
    status_changed_at TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    CHECK (expiry_date >= collected_at),
    CHECK (status <> 'reserved' OR request_id IS NOT NULL OR exchange_id IS NOT NULL)
);

CREATE TABLE inventory_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL,
    unit_id     INTEGER REFERENCES blood_units(id),
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    blood_group TEXT NOT NULL CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    event_type  TEXT NOT NULL CHECK (event_type IN ('received','reserved','released','issued','transfused',
                                                     'expired','discarded','transferred_out','transferred_in')),
    request_id  INTEGER REFERENCES blood_requests(id),
    actor_id    INTEGER REFERENCES users(id),
    note        TEXT
);

-- Hospital-to-hospital loans: the units move on creation and must be returned by the deadline.
CREATE TABLE contracts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id           TEXT NOT NULL UNIQUE,
    lending_hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    borrowing_hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
    blood_group         TEXT NOT NULL CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    units               INTEGER NOT NULL CHECK (units > 0),
    created_at          TEXT NOT NULL,
    return_deadline     TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','RETURNED','BREACHED','CANCELLED')),
    returned_at         TEXT,
    created_by          INTEGER REFERENCES users(id),
    CHECK (lending_hospital_id <> borrowing_hospital_id)
);

CREATE TABLE screening_tests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id    INTEGER REFERENCES donors(id),
    hospital_id INTEGER REFERENCES hospitals(id),
    test_date   TEXT NOT NULL,
    hiv         INTEGER NOT NULL DEFAULT 0 CHECK (hiv IN (0,1)),
    hepatitis_b INTEGER NOT NULL DEFAULT 0 CHECK (hepatitis_b IN (0,1)),
    hepatitis_c INTEGER NOT NULL DEFAULT 0 CHECK (hepatitis_c IN (0,1)),
    syphilis    INTEGER NOT NULL DEFAULT 0 CHECK (syphilis IN (0,1)),
    malaria     INTEGER NOT NULL DEFAULT 0 CHECK (malaria IN (0,1)),
    result      TEXT NOT NULL DEFAULT 'PENDING' CHECK (result IN ('PASS','FAIL','PENDING')),
    decision    TEXT CHECK (decision IS NULL OR decision IN ('SAFE','DEFER','BLOCK')),
    risk_score  INTEGER CHECK (risk_score IS NULL OR risk_score BETWEEN 0 AND 100),
    created_by  INTEGER REFERENCES users(id)
);

-- Append-only (see triggers below).
CREATE TABLE audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,
    description TEXT NOT NULL,
    user_id     INTEGER REFERENCES users(id),
    timestamp   TEXT NOT NULL,
    entity_type TEXT,
    entity_id   TEXT,
    before_json TEXT,
    after_json  TEXT
);

CREATE TABLE ai_logs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    feature          TEXT NOT NULL,
    input_summary    TEXT,
    response_preview TEXT,
    hospital_id      INTEGER REFERENCES hospitals(id),
    user_id          INTEGER REFERENCES users(id),
    created_at       TEXT NOT NULL
);

-- Rows a migration could not carry over (invalid group, missing expiry, ...). Nothing is silently dropped.
CREATE TABLE migration_rejects (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table TEXT NOT NULL,
    row_json     TEXT NOT NULL,
    reason       TEXT NOT NULL,
    migrated_at  TEXT NOT NULL
);

CREATE INDEX ix_users_hospital ON users(hospital_id);
CREATE UNIQUE INDEX ux_donors_cnic ON donors(cnic) WHERE cnic IS NOT NULL AND cnic <> '';
CREATE INDEX ix_donors_hospital ON donors(hospital_id);
CREATE INDEX ix_requests_hospital ON blood_requests(requesting_hospital_id);
CREATE INDEX ix_requests_status ON blood_requests(status);
CREATE INDEX ix_transfusions_hospital ON transfusions(hospital_id, transfused_at);
CREATE INDEX ix_exchanges_from ON exchanges(from_hospital_id);
CREATE INDEX ix_exchanges_to ON exchanges(to_hospital_id);
CREATE INDEX ix_exchanges_status ON exchanges(status);
CREATE INDEX ix_units_stock ON blood_units(hospital_id, blood_group, status);
CREATE INDEX ix_units_expiry ON blood_units(expiry_date);
CREATE INDEX ix_units_status ON blood_units(status);
CREATE INDEX ix_units_request ON blood_units(request_id) WHERE request_id IS NOT NULL;
CREATE INDEX ix_units_exchange ON blood_units(exchange_id) WHERE exchange_id IS NOT NULL;
CREATE INDEX ix_events_hospital_at ON inventory_events(hospital_id, at);
CREATE INDEX ix_events_type_at ON inventory_events(event_type, at);
CREATE INDEX ix_events_unit ON inventory_events(unit_id);
CREATE INDEX ix_contracts_lender ON contracts(lending_hospital_id);
CREATE INDEX ix_contracts_borrower ON contracts(borrowing_hospital_id);
CREATE INDEX ix_contracts_status_deadline ON contracts(status, return_deadline);
CREATE INDEX ix_screening_donor ON screening_tests(donor_id);
CREATE INDEX ix_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX ix_audit_user ON audit_logs(user_id);
CREATE INDEX ix_audit_entity ON audit_logs(entity_type, entity_id);

-- A unit can only move along the allowed status transitions (mirrors lifeline.constants.ALLOWED_TRANSITIONS).
CREATE TRIGGER trg_units_state_machine BEFORE UPDATE OF status ON blood_units
WHEN NEW.status <> OLD.status AND NOT (
       (OLD.status = 'available' AND NEW.status IN ('reserved','issued','transfused','expired','discarded'))
    OR (OLD.status = 'reserved'  AND NEW.status IN ('available','issued','transfused','expired','discarded'))
    OR (OLD.status = 'issued'    AND NEW.status IN ('transfused','discarded'))
)
BEGIN
    SELECT RAISE(ABORT, 'invalid blood unit status transition');
END;

-- What a unit is must never be edited after the fact: relabelling a group or moving an expiry is a safety event.
CREATE TRIGGER trg_units_group_immutable BEFORE UPDATE OF blood_group ON blood_units
WHEN NEW.blood_group <> OLD.blood_group
BEGIN
    SELECT RAISE(ABORT, 'blood group of a unit cannot be changed');
END;

CREATE TRIGGER trg_units_expiry_immutable BEFORE UPDATE OF expiry_date ON blood_units
WHEN NEW.expiry_date <> OLD.expiry_date
BEGIN
    SELECT RAISE(ABORT, 'expiry date of a unit cannot be changed');
END;

CREATE TRIGGER trg_audit_no_update BEFORE UPDATE ON audit_logs
BEGIN
    SELECT RAISE(ABORT, 'audit log is append-only');
END;

CREATE TRIGGER trg_audit_no_delete BEFORE DELETE ON audit_logs
BEGIN
    SELECT RAISE(ABORT, 'audit log is append-only');
END;
