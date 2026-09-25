-- Frozen copy of the schema at user_version 1 (before the unit ledger), used to test migration 002.
CREATE TABLE hospitals (
        id          INTEGER PRIMARY KEY,
        name        TEXT NOT NULL,
        city        TEXT NOT NULL,
        address     TEXT,
        latitude    REAL,
        longitude   REAL,
        phone       TEXT
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

    CREATE TABLE blood_units (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        hospital_id  INTEGER NOT NULL REFERENCES hospitals(id),
        blood_group  TEXT NOT NULL,
        units        INTEGER NOT NULL DEFAULT 0,
        expiry_date  TEXT,
        updated_at   TEXT NOT NULL
    );

    CREATE TABLE donors (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT NOT NULL,
        cnic         TEXT,
        phone        TEXT,
        blood_group  TEXT NOT NULL,
        hospital_id  INTEGER REFERENCES hospitals(id),
        last_donated TEXT,
        eligible     INTEGER DEFAULT 1,
        notes        TEXT
    );

    CREATE TABLE blood_requests (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        requesting_hospital_id INTEGER NOT NULL REFERENCES hospitals(id),
        blood_group           TEXT NOT NULL,
        units_needed          INTEGER NOT NULL,
        urgency               TEXT DEFAULT 'ROUTINE',
        status                TEXT DEFAULT 'PENDING',
        patient_name          TEXT,
        patient_condition     TEXT,
        created_at            TEXT NOT NULL,
        resolved_at           TEXT
    );

    CREATE TABLE transfusions (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        hospital_id  INTEGER NOT NULL REFERENCES hospitals(id),
        patient_name TEXT,
        blood_group  TEXT NOT NULL,
        units        INTEGER NOT NULL,
        transfused_at TEXT NOT NULL,
        performed_by TEXT,
        notes        TEXT
    );

    CREATE TABLE exchanges (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        from_hospital_id     INTEGER NOT NULL REFERENCES hospitals(id),
        to_hospital_id       INTEGER NOT NULL REFERENCES hospitals(id),
        blood_group          TEXT NOT NULL,
        units                INTEGER NOT NULL,
        status               TEXT DEFAULT 'PENDING',
        created_at           TEXT NOT NULL,
        completed_at         TEXT
    );

    CREATE TABLE contracts (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        hospital_id  INTEGER NOT NULL REFERENCES hospitals(id),
        vendor_name  TEXT NOT NULL,
        blood_group  TEXT NOT NULL,
        units_per_month INTEGER NOT NULL,
        contract_start TEXT,
        contract_end   TEXT,
        status         TEXT DEFAULT 'ACTIVE'
    );

    CREATE TABLE screening_tests (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        donor_id    INTEGER REFERENCES donors(id),
        hospital_id INTEGER REFERENCES hospitals(id),
        test_date   TEXT NOT NULL,
        hiv         INTEGER DEFAULT 0,
        hepatitis_b INTEGER DEFAULT 0,
        hepatitis_c INTEGER DEFAULT 0,
        syphilis    INTEGER DEFAULT 0,
        malaria     INTEGER DEFAULT 0,
        result      TEXT DEFAULT 'PENDING'
    );

    CREATE TABLE audit_logs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        action_type TEXT NOT NULL,
        description TEXT NOT NULL,
        user_id     INTEGER REFERENCES users(id),
        timestamp   TEXT NOT NULL
    );

    CREATE TABLE inventory_changes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        hospital_id INTEGER REFERENCES hospitals(id),
        blood_group TEXT NOT NULL,
        change_type TEXT NOT NULL,
        units_delta INTEGER NOT NULL,
        reason      TEXT,
        changed_at  TEXT NOT NULL,
        changed_by  INTEGER REFERENCES users(id)
    );

    CREATE TABLE patients (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        name               TEXT NOT NULL,
        age                INTEGER,
        blood_group        TEXT NOT NULL,
        cnic               TEXT,
        phone              TEXT,
        condition          TEXT,
        admission_date     TEXT,
        discharge_date     TEXT,
        hospital_id        INTEGER NOT NULL REFERENCES hospitals(id),
        attending_physician TEXT,
        notes              TEXT
    );

    CREATE TABLE ai_logs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        feature     TEXT NOT NULL,
        input_summary TEXT,
        response_preview TEXT,
        hospital_id INTEGER REFERENCES hospitals(id),
        user_id     INTEGER REFERENCES users(id),
        created_at  TEXT NOT NULL
    );

    CREATE TABLE login_throttle (
        email        TEXT PRIMARY KEY,
        failed_count INTEGER NOT NULL DEFAULT 0,
        locked_until INTEGER NOT NULL DEFAULT 0,
        updated_at   INTEGER NOT NULL
    );
