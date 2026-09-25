-- Schema v2: per-unit blood ledger, state machine, CHECK constraints, indexes, lend/borrow contracts,
-- inventory events, append-only audit log with entity/before/after.
--
-- Generated from lifeline/db/schema.sql (DDL) and then frozen: never edit an applied migration, add 003.
-- Rows that break the new constraints are copied to migration_rejects, not dropped. The runner turns
-- foreign_keys OFF around this file and runs PRAGMA foreign_key_check afterwards.
BEGIN;

CREATE TABLE migration_rejects (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table TEXT NOT NULL,
    row_json     TEXT NOT NULL,
    reason       TEXT NOT NULL,
    migrated_at  TEXT NOT NULL
);

-- hospitals: + stock_status, UNIQUE name, coordinate ranges
CREATE TABLE hospitals_new (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    city         TEXT NOT NULL,
    address      TEXT,
    latitude     REAL CHECK (latitude BETWEEN -90 AND 90),
    longitude    REAL CHECK (longitude BETWEEN -180 AND 180),
    phone        TEXT,
    stock_status TEXT NOT NULL DEFAULT 'ok' CHECK (stock_status IN ('ok','low','critical'))
);
INSERT INTO hospitals_new (id, name, city, address, latitude, longitude, phone)
SELECT id, name, city, address, latitude, longitude, phone FROM hospitals;
DROP TABLE hospitals;
ALTER TABLE hospitals_new RENAME TO hospitals;

-- donors: + age, times_donated, CHECKs, unique CNIC
CREATE TABLE donors_new (
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
CREATE TEMP VIEW v_donors_ok AS
SELECT d.id FROM donors d
WHERE d.blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')
  AND COALESCE(TRIM(d.name), '') <> ''
  AND (d.hospital_id IS NULL OR d.hospital_id IN (SELECT id FROM hospitals))
  AND COALESCE(d.eligible, 1) IN (0, 1)
  AND NOT (COALESCE(d.cnic, '') <> '' AND EXISTS (SELECT 1 FROM donors d2 WHERE d2.cnic = d.cnic AND d2.id < d.id));
INSERT INTO migration_rejects (source_table, row_json, reason, migrated_at)
SELECT 'donors', json_object('id', id, 'name', name, 'cnic', cnic, 'phone', phone, 'blood_group', blood_group, 'hospital_id', hospital_id, 'last_donated', last_donated, 'eligible', eligible, 'notes', notes), 'invalid blood group, name, hospital, eligibility flag or duplicate CNIC', strftime('%Y-%m-%dT%H:%M:%S','now','+5 hours') || '+05:00'
FROM donors WHERE id NOT IN (SELECT id FROM v_donors_ok);
INSERT INTO donors_new (id, name, cnic, phone, blood_group, hospital_id, last_donated, eligible, notes)
SELECT id, name, cnic, phone, blood_group, hospital_id, last_donated, COALESCE(eligible, 1), notes
FROM donors WHERE id IN (SELECT id FROM v_donors_ok);
DROP VIEW v_donors_ok;
DROP TABLE donors;
ALTER TABLE donors_new RENAME TO donors;

-- blood_requests: CHECKs, RESERVED/CANCELLED states, created_by
CREATE TABLE blood_requests_new (
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
CREATE TEMP VIEW v_requests_ok AS
SELECT r.id FROM blood_requests r
WHERE r.blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-') AND r.units_needed > 0
  AND r.requesting_hospital_id IN (SELECT id FROM hospitals);
INSERT INTO migration_rejects (source_table, row_json, reason, migrated_at)
SELECT 'blood_requests', json_object('id', id, 'requesting_hospital_id', requesting_hospital_id, 'blood_group', blood_group, 'units_needed', units_needed, 'urgency', urgency, 'status', status, 'patient_name', patient_name, 'patient_condition', patient_condition, 'created_at', created_at, 'resolved_at', resolved_at), 'invalid blood group, units or hospital', strftime('%Y-%m-%dT%H:%M:%S','now','+5 hours') || '+05:00'
FROM blood_requests WHERE id NOT IN (SELECT id FROM v_requests_ok);
INSERT INTO blood_requests_new (id, requesting_hospital_id, blood_group, units_needed, urgency, status,
                                patient_name, patient_condition, created_at, resolved_at)
SELECT id, requesting_hospital_id, blood_group, units_needed,
       CASE WHEN urgency IN ('CRITICAL','URGENT','ROUTINE') THEN urgency ELSE 'ROUTINE' END,
       CASE WHEN status IN ('PENDING','RESERVED','RESOLVED','CANCELLED') THEN status ELSE 'PENDING' END,
       patient_name, patient_condition, created_at, resolved_at
FROM blood_requests WHERE id IN (SELECT id FROM v_requests_ok);
DROP VIEW v_requests_ok;
DROP TABLE blood_requests;
ALTER TABLE blood_requests_new RENAME TO blood_requests;

-- transfusions: + patient_blood_group, created_by, CHECKs
CREATE TABLE transfusions_new (
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
CREATE TEMP VIEW v_transfusions_ok AS
SELECT t.id FROM transfusions t
WHERE t.blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-') AND t.units > 0 AND t.hospital_id IN (SELECT id FROM hospitals);
INSERT INTO migration_rejects (source_table, row_json, reason, migrated_at)
SELECT 'transfusions', json_object('id', id, 'hospital_id', hospital_id, 'patient_name', patient_name, 'blood_group', blood_group, 'units', units, 'transfused_at', transfused_at, 'performed_by', performed_by, 'notes', notes), 'invalid blood group, units or hospital', strftime('%Y-%m-%dT%H:%M:%S','now','+5 hours') || '+05:00'
FROM transfusions WHERE id NOT IN (SELECT id FROM v_transfusions_ok);
INSERT INTO transfusions_new (id, hospital_id, patient_name, blood_group, units, transfused_at, performed_by, notes)
SELECT id, hospital_id, patient_name, blood_group, units, transfused_at, performed_by, notes
FROM transfusions WHERE id IN (SELECT id FROM v_transfusions_ok);
DROP VIEW v_transfusions_ok;
DROP TABLE transfusions;
ALTER TABLE transfusions_new RENAME TO transfusions;

-- exchanges: status set, CHECKs, requested_by/decided_by
CREATE TABLE exchanges_new (
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
CREATE TEMP VIEW v_exchanges_ok AS
SELECT e.id FROM exchanges e
WHERE e.blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-') AND e.units > 0 AND e.from_hospital_id <> e.to_hospital_id
  AND e.from_hospital_id IN (SELECT id FROM hospitals) AND e.to_hospital_id IN (SELECT id FROM hospitals);
INSERT INTO migration_rejects (source_table, row_json, reason, migrated_at)
SELECT 'exchanges', json_object('id', id, 'from_hospital_id', from_hospital_id, 'to_hospital_id', to_hospital_id, 'blood_group', blood_group, 'units', units, 'status', status, 'created_at', created_at, 'completed_at', completed_at), 'invalid blood group, units or hospitals', strftime('%Y-%m-%dT%H:%M:%S','now','+5 hours') || '+05:00'
FROM exchanges WHERE id NOT IN (SELECT id FROM v_exchanges_ok);
INSERT INTO exchanges_new (id, from_hospital_id, to_hospital_id, blood_group, units, status, created_at, completed_at)
SELECT id, from_hospital_id, to_hospital_id, blood_group, units,
       CASE WHEN status IN ('PENDING','ACCEPTED','COMPLETED','REJECTED','CANCELLED') THEN status ELSE 'PENDING' END,
       created_at, completed_at
FROM exchanges WHERE id IN (SELECT id FROM v_exchanges_ok);
DROP VIEW v_exchanges_ok;
DROP TABLE exchanges;
ALTER TABLE exchanges_new RENAME TO exchanges;

-- screening_tests: + decision, risk_score, created_by, CHECKs
CREATE TABLE screening_tests_new (
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
CREATE TEMP VIEW v_screening_ok AS
SELECT s.id FROM screening_tests s
WHERE COALESCE(s.hiv, 0) IN (0,1) AND COALESCE(s.hepatitis_b, 0) IN (0,1) AND COALESCE(s.hepatitis_c, 0) IN (0,1)
  AND COALESCE(s.syphilis, 0) IN (0,1) AND COALESCE(s.malaria, 0) IN (0,1)
  AND (s.hospital_id IS NULL OR s.hospital_id IN (SELECT id FROM hospitals));
INSERT INTO migration_rejects (source_table, row_json, reason, migrated_at)
SELECT 'screening_tests', json_object('id', id, 'donor_id', donor_id, 'hospital_id', hospital_id, 'test_date', test_date, 'hiv', hiv, 'hepatitis_b', hepatitis_b, 'hepatitis_c', hepatitis_c, 'syphilis', syphilis, 'malaria', malaria, 'result', result), 'invalid flag or hospital', strftime('%Y-%m-%dT%H:%M:%S','now','+5 hours') || '+05:00'
FROM screening_tests WHERE id NOT IN (SELECT id FROM v_screening_ok);
INSERT INTO screening_tests_new (id, donor_id, hospital_id, test_date, hiv, hepatitis_b, hepatitis_c, syphilis, malaria, result)
SELECT id, CASE WHEN donor_id IN (SELECT id FROM donors) THEN donor_id END, hospital_id, test_date,
       COALESCE(hiv, 0), COALESCE(hepatitis_b, 0), COALESCE(hepatitis_c, 0), COALESCE(syphilis, 0), COALESCE(malaria, 0),
       CASE WHEN result IN ('PASS','FAIL','PENDING') THEN result ELSE 'PENDING' END
FROM screening_tests WHERE id IN (SELECT id FROM v_screening_ok);
DROP VIEW v_screening_ok;
DROP TABLE screening_tests;
ALTER TABLE screening_tests_new RENAME TO screening_tests;

-- blood_units: (hospital, group, expiry, count) rows become one row per unit
CREATE TABLE blood_units_new (
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
CREATE TEMP VIEW v_units_ok AS
SELECT b.id FROM blood_units b
WHERE b.blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-') AND COALESCE(b.units, 0) >= 0
  AND b.hospital_id IN (SELECT id FROM hospitals)
  AND b.expiry_date IS NOT NULL AND date(b.expiry_date) IS NOT NULL;
INSERT INTO migration_rejects (source_table, row_json, reason, migrated_at)
SELECT 'blood_units', json_object('id', id, 'hospital_id', hospital_id, 'blood_group', blood_group, 'units', units, 'expiry_date', expiry_date, 'updated_at', updated_at), 'invalid blood group, negative units, unknown hospital or missing/invalid expiry date', strftime('%Y-%m-%dT%H:%M:%S','now','+5 hours') || '+05:00'
FROM blood_units WHERE id NOT IN (SELECT id FROM v_units_ok);
WITH RECURSIVE seq(n) AS (
    SELECT 1 UNION ALL SELECT n + 1 FROM seq WHERE n < (SELECT COALESCE(MAX(units), 0) FROM blood_units)
)
INSERT INTO blood_units_new (unit_code, hospital_id, blood_group, collected_at, expiry_date, status, status_changed_at, created_at)
SELECT 'MIG-' || b.id || '-' || seq.n, b.hospital_id, b.blood_group,
       CASE WHEN date(b.updated_at) IS NOT NULL AND date(b.updated_at) <= date(b.expiry_date)
            THEN date(b.updated_at) ELSE date(b.expiry_date) END,
       date(b.expiry_date),
       CASE WHEN date(b.expiry_date) < date('now', '+5 hours') THEN 'expired' ELSE 'available' END,
       strftime('%Y-%m-%dT%H:%M:%S','now','+5 hours') || '+05:00', strftime('%Y-%m-%dT%H:%M:%S','now','+5 hours') || '+05:00'
FROM blood_units b JOIN seq ON seq.n <= b.units
WHERE b.id IN (SELECT id FROM v_units_ok);
UPDATE blood_units_new SET unit_code = 'U' || printf('%07d', id) WHERE unit_code LIKE 'MIG-%';
DROP VIEW v_units_ok;
DROP TABLE blood_units;
ALTER TABLE blood_units_new RENAME TO blood_units;

-- inventory_changes (signed deltas) become one inventory_events row per unit moved
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
WITH RECURSIVE seq(n) AS (
    SELECT 1 UNION ALL SELECT n + 1 FROM seq WHERE n < (SELECT COALESCE(MAX(ABS(units_delta)), 0) FROM inventory_changes)
)
INSERT INTO inventory_events (at, hospital_id, blood_group, event_type, actor_id, note)
SELECT c.changed_at, c.hospital_id, c.blood_group,
       CASE WHEN c.units_delta > 0 THEN 'received' ELSE 'issued' END,
       CASE WHEN c.changed_by IN (SELECT id FROM users) THEN c.changed_by END,
       'legacy: ' || COALESCE(c.reason, '')
FROM inventory_changes c JOIN seq ON seq.n <= ABS(c.units_delta)
WHERE c.hospital_id IN (SELECT id FROM hospitals) AND c.blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-') AND c.units_delta <> 0;
INSERT INTO migration_rejects (source_table, row_json, reason, migrated_at)
SELECT 'inventory_changes', json_object('id', id, 'hospital_id', hospital_id, 'blood_group', blood_group,
       'units_delta', units_delta, 'reason', reason, 'changed_at', changed_at), 'invalid group, hospital or zero delta', strftime('%Y-%m-%dT%H:%M:%S','now','+5 hours') || '+05:00'
FROM inventory_changes
WHERE NOT (hospital_id IN (SELECT id FROM hospitals) AND blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-') AND units_delta <> 0);
DROP TABLE inventory_changes;

-- contracts: the old vendor-supply table is kept as vendor_contracts_legacy; contracts now models loans
ALTER TABLE contracts RENAME TO vendor_contracts_legacy;
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

-- audit_logs: entity + before/after
ALTER TABLE audit_logs ADD COLUMN entity_type TEXT;
ALTER TABLE audit_logs ADD COLUMN entity_id TEXT;
ALTER TABLE audit_logs ADD COLUMN before_json TEXT;
ALTER TABLE audit_logs ADD COLUMN after_json TEXT;

-- indexes
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

-- triggers
CREATE TRIGGER trg_units_state_machine BEFORE UPDATE OF status ON blood_units
WHEN NEW.status <> OLD.status AND NOT (
       (OLD.status = 'available' AND NEW.status IN ('reserved','issued','transfused','expired','discarded'))
    OR (OLD.status = 'reserved'  AND NEW.status IN ('available','issued','transfused','expired','discarded'))
    OR (OLD.status = 'issued'    AND NEW.status IN ('transfused','discarded'))
)
BEGIN
    SELECT RAISE(ABORT, 'invalid blood unit status transition');
END;

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

PRAGMA user_version = 2;
COMMIT;
