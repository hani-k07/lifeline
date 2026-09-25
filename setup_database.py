# setup_database.py
"""
LIFELINE v6.0 — Database Setup & Seeding

    python setup_database.py           create + seed a new DB, or migrate an existing one (non-destructive)
    python setup_database.py --reset   delete the DB and reseed it
"""
from __future__ import annotations
import argparse
import sqlite3
import hashlib
from datetime import datetime, timedelta
import random

from lifeline.auth.roles import Role
from lifeline.config import get_settings
from lifeline.db.migrate import LATEST_VERSION, apply_migrations

DB_PATH = get_settings().db_path
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS hospitals (
        id          INTEGER PRIMARY KEY,
        name        TEXT NOT NULL,
        city        TEXT NOT NULL,
        address     TEXT,
        latitude    REAL,
        longitude   REAL,
        phone       TEXT
    );

    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        email         TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL CHECK(role IN ('super_admin','hospital_admin','staff')),
        name          TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        hospital_id   INTEGER REFERENCES hospitals(id)
    );

    CREATE TABLE IF NOT EXISTS blood_units (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        hospital_id  INTEGER NOT NULL REFERENCES hospitals(id),
        blood_group  TEXT NOT NULL,
        units        INTEGER NOT NULL DEFAULT 0,
        expiry_date  TEXT,
        updated_at   TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS donors (
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

    CREATE TABLE IF NOT EXISTS blood_requests (
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

    CREATE TABLE IF NOT EXISTS transfusions (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        hospital_id  INTEGER NOT NULL REFERENCES hospitals(id),
        patient_name TEXT,
        blood_group  TEXT NOT NULL,
        units        INTEGER NOT NULL,
        transfused_at TEXT NOT NULL,
        performed_by TEXT,
        notes        TEXT
    );

    CREATE TABLE IF NOT EXISTS exchanges (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        from_hospital_id     INTEGER NOT NULL REFERENCES hospitals(id),
        to_hospital_id       INTEGER NOT NULL REFERENCES hospitals(id),
        blood_group          TEXT NOT NULL,
        units                INTEGER NOT NULL,
        status               TEXT DEFAULT 'PENDING',
        created_at           TEXT NOT NULL,
        completed_at         TEXT
    );

    CREATE TABLE IF NOT EXISTS contracts (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        hospital_id  INTEGER NOT NULL REFERENCES hospitals(id),
        vendor_name  TEXT NOT NULL,
        blood_group  TEXT NOT NULL,
        units_per_month INTEGER NOT NULL,
        contract_start TEXT,
        contract_end   TEXT,
        status         TEXT DEFAULT 'ACTIVE'
    );

    CREATE TABLE IF NOT EXISTS screening_tests (
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

    CREATE TABLE IF NOT EXISTS audit_logs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        action_type TEXT NOT NULL,
        description TEXT NOT NULL,
        user_id     INTEGER REFERENCES users(id),
        timestamp   TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS inventory_changes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        hospital_id INTEGER REFERENCES hospitals(id),
        blood_group TEXT NOT NULL,
        change_type TEXT NOT NULL,
        units_delta INTEGER NOT NULL,
        reason      TEXT,
        changed_at  TEXT NOT NULL,
        changed_by  INTEGER REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS patients (
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

    CREATE TABLE IF NOT EXISTS ai_logs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        feature     TEXT NOT NULL,
        input_summary TEXT,
        response_preview TEXT,
        hospital_id INTEGER REFERENCES hospitals(id),
        user_id     INTEGER REFERENCES users(id),
        created_at  TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS login_throttle (
        email        TEXT PRIMARY KEY,
        failed_count INTEGER NOT NULL DEFAULT 0,
        locked_until INTEGER NOT NULL DEFAULT 0,
        updated_at   INTEGER NOT NULL
    );
    """)
    conn.execute(f"PRAGMA user_version = {LATEST_VERSION}")   # fresh schema already includes every migration
    conn.commit()


def seed_hospitals(conn: sqlite3.Connection) -> None:
    hospitals = [
        (1, "Mayo Hospital",     "Lahore", "Nila Gumbad, Lahore",        31.5651, 74.3062, "+92-42-99200600"),
        (2, "Services Hospital", "Lahore", "Sir Ganga Ram Hospital Rd",  31.5497, 74.3436, "+92-42-99203000"),
        (3, "Jinnah Hospital",   "Lahore", "Allama Iqbal Road, Lahore",  31.5204, 74.3587, "+92-42-99231301"),
        (4, "Shaukat Khanum",    "Lahore", "7-A Johar Town, Lahore",     31.4697, 74.2728, "+92-42-35945100"),
        (5, "Lahore General",    "Lahore", "Jail Road, Lahore",          31.5560, 74.3288, "+92-42-99231601"),
        (6, "CMH Lahore",        "Lahore", "Mall Road, Lahore",          31.5533, 74.3441, "+92-42-111-001"),
        (7, "Sheikh Zayed",      "Lahore", "Canal Bank Road, Lahore",    31.4982, 74.3153, "+92-42-111-002"),
        (8, "Ittefaq Hospital",  "Lahore", "Model Town, Lahore",         31.4829, 74.3284, "+92-42-111-003"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO hospitals (id,name,city,address,latitude,longitude,phone) VALUES (?,?,?,?,?,?,?)",
        hospitals
    )
    conn.commit()


def seed_users(conn: sqlite3.Connection) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    pw = hash_password("lifeline123")
    users = [
        ("admin@lifeline.com",            pw, Role.SUPER_ADMIN.value, "Dr. Zara Ahmed (Admin)",          now, None),
        ("mayo@lifeline.com",             pw, Role.HOSPITAL_ADMIN.value, "Dr. Kamran Sheikh (Mayo)",         now, 1),
        ("services@lifeline.com",         pw, Role.HOSPITAL_ADMIN.value, "Dr. Amna Malik (Services)",        now, 2),
        ("jinnah@lifeline.com",           pw, Role.HOSPITAL_ADMIN.value, "Dr. Bilal Hassan (Jinnah)",        now, 3),
        ("shaukat@lifeline.com",          pw, Role.HOSPITAL_ADMIN.value, "Dr. Sara Yousaf (Shaukat)",        now, 4),
        ("mayo.worker@lifeline.com",      pw, Role.STAFF.value, "Nurse Hira Baig (Mayo)",           now, 1),
        ("mayo.worker2@lifeline.com",     pw, Role.STAFF.value, "Technician Saad Ali (Mayo)",       now, 1),
        ("services.worker@lifeline.com",  pw, Role.STAFF.value, "Nurse Rabia Naz (Services)",       now, 2),
        ("jinnah.worker@lifeline.com",    pw, Role.STAFF.value, "Technician Umar Farooq (Jinnah)",  now, 3),
        ("shaukat.worker@lifeline.com",   pw, Role.STAFF.value, "Nurse Fatima Zia (Shaukat)",       now, 4),
        ("shaukat.worker2@lifeline.com",  pw, Role.STAFF.value, "Technician Ali Hamza (Shaukat)",   now, 4),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO users (email,password_hash,role,name,created_at,hospital_id) VALUES (?,?,?,?,?,?)",
        users,
    )
    conn.commit()


def seed_blood_inventory(conn: sqlite3.Connection) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    random.seed(42)
    rows = []
    for hosp_id in range(1, 9):
        for bg in BLOOD_GROUPS:
            units = random.randint(0, 60)
            expiry = (datetime.now() + timedelta(days=random.randint(5, 35))).strftime("%Y-%m-%d")
            rows.append((hosp_id, bg, units, expiry, now))
    conn.executemany(
        "INSERT INTO blood_units (hospital_id,blood_group,units,expiry_date,updated_at) VALUES (?,?,?,?,?)",
        rows
    )
    conn.commit()


def seed_donors(conn: sqlite3.Connection) -> None:
    sample_donors = [
        ("Ahmed Raza",    "35202-1234567-1", "0300-1234567", "O+",  1, "2024-11-01"),
        ("Fatima Noor",   "35202-2345678-2", "0301-2345678", "A+",  1, "2024-10-15"),
        ("Bilal Khan",    "35202-3456789-3", "0302-3456789", "B+",  2, "2024-12-01"),
        ("Sara Malik",    "35202-4567890-4", "0303-4567890", "AB+", 2, "2024-09-20"),
        ("Umar Farooq",   "35202-5678901-5", "0304-5678901", "O-",  3, "2025-01-10"),
        ("Zainab Ali",    "35202-6789012-6", "0305-6789012", "A-",  3, "2024-11-25"),
        ("Hassan Shah",   "35202-7890123-7", "0306-7890123", "B-",  4, "2025-02-01"),
        ("Ayesha Iqbal",  "35202-8901234-8", "0307-8901234", "O+",  4, "2024-10-05"),
        ("Imran Butt",    "35202-9012345-9", "0308-9012345", "A+",  1, "2025-01-20"),
        ("Nadia Hussain", "35202-0123456-0", "0309-0123456", "B+",  2, "2024-12-15"),
    ]
    conn.executemany(
        "INSERT INTO donors (name,cnic,phone,blood_group,hospital_id,last_donated,eligible) VALUES (?,?,?,?,?,?,1)",
        sample_donors
    )
    conn.commit()


def seed_sample_requests(conn: sqlite3.Connection) -> None:
    """Seed some sample blood requests for demo purposes."""
    now = datetime.now()
    requests_data = [
        (1, "A+",  3, "CRITICAL", "PENDING",  "Ali Hassan",    "Trauma surgery",  (now - timedelta(hours=2)).isoformat(timespec="seconds")),
        (2, "O-",  5, "URGENT",   "PENDING",  "Maria Khan",    "Childbirth",      (now - timedelta(hours=1)).isoformat(timespec="seconds")),
        (3, "B+",  2, "ROUTINE",  "PENDING",  "Jamil Ahmed",   "Elective surgery",(now - timedelta(minutes=30)).isoformat(timespec="seconds")),
        (1, "AB+", 4, "URGENT",   "RESOLVED", "Saira Bibi",    "Cancer treatment",(now - timedelta(days=1)).isoformat(timespec="seconds")),
        (4, "O+",  6, "CRITICAL", "PENDING",  "Usman Tariq",   "Road accident",   (now - timedelta(minutes=10)).isoformat(timespec="seconds")),
    ]
    conn.executemany(
        "INSERT INTO blood_requests (requesting_hospital_id,blood_group,units_needed,urgency,status,patient_name,patient_condition,created_at) VALUES (?,?,?,?,?,?,?,?)",
        requests_data
    )
    conn.commit()


def seed_audit_logs(conn: sqlite3.Connection) -> None:
    """Seed some sample audit log entries."""
    now = datetime.now()
    logs = [
        ("LOGIN",          "User admin@lifeline.com logged in",          1, (now - timedelta(minutes=5)).isoformat(timespec="seconds")),
        ("INVENTORY_ADD",  "Added 10 units of O+ at Mayo Hospital",      2, (now - timedelta(hours=1)).isoformat(timespec="seconds")),
        ("EMERGENCY_REQ",  "Emergency request for A+ blood at Services",  3, (now - timedelta(hours=2)).isoformat(timespec="seconds")),
        ("TRANSFUSION",    "Transfusion of B+ completed at Jinnah",       4, (now - timedelta(hours=3)).isoformat(timespec="seconds")),
        ("LOGIN",          "User mayo@lifeline.com logged in",            2, (now - timedelta(hours=4)).isoformat(timespec="seconds")),
    ]
    conn.executemany(
        "INSERT INTO audit_logs (action_type,description,user_id,timestamp) VALUES (?,?,?,?)",
        logs
    )
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create/seed or migrate the LIFELINE database.")
    parser.add_argument("--reset", action="store_true", help="delete the existing database and reseed it")
    args = parser.parse_args()

    print("[*] LIFELINE v6.0 -- Database Setup")
    if DB_PATH.exists() and not args.reset:
        conn = sqlite3.connect(DB_PATH)
        applied = apply_migrations(conn)
        conn.close()
        print(f"   -> Existing database kept ({'migrated to v' + str(applied[-1]) if applied else 'already up to date'}).")
        print("   -> Use --reset to delete and reseed it.")
        return
    if args.reset and DB_PATH.exists():
        DB_PATH.unlink()
        for suffix in ("-wal", "-shm", "-journal"):
            DB_PATH.with_name(DB_PATH.name + suffix).unlink(missing_ok=True)
        print("   -> Old database deleted.")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    print("   -> Creating schema...")
    create_schema(conn)
    print("   -> Seeding hospitals...")
    seed_hospitals(conn)
    print("   -> Seeding users (11 accounts)...")
    seed_users(conn)
    print("   -> Seeding blood inventory...")
    seed_blood_inventory(conn)
    print("   -> Seeding sample donors...")
    seed_donors(conn)
    print("   -> Seeding sample requests...")
    seed_sample_requests(conn)
    print("   -> Seeding audit logs...")
    seed_audit_logs(conn)
    conn.close()
    print()
    print("[+] Database ready: lifeline.db")
    print("   Run: streamlit run app.py")


if __name__ == "__main__":
    main()
