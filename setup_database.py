import sqlite3
import uuid
import hashlib
import os
from datetime import datetime, timedelta

DB_PATH = "lifeline.db"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def add_missing_columns():
    """Add new columns to existing tables without destroying data."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get existing columns for users table
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [row[1] for row in cursor.fetchall()]
    
    user_new_cols = {
        "phone_number": "TEXT DEFAULT ''",
        "employee_id":  "TEXT DEFAULT ''",
        "department":   "TEXT DEFAULT 'Blood Bank'",
        "shift":        "TEXT DEFAULT 'Morning'",
        "is_active":    "INTEGER DEFAULT 1",
    }
    for col, definition in user_new_cols.items():
        if col not in user_cols:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
    
    # Get existing columns for hospitals table
    cursor.execute("PRAGMA table_info(hospitals)")
    hosp_cols = [row[1] for row in cursor.fetchall()]
    
    hosp_new_cols = {
        "hospital_type": "TEXT DEFAULT 'Public'",
        "status":        "TEXT DEFAULT 'active'",
    }
    for col, definition in hosp_new_cols.items():
        if col not in hosp_cols:
            cursor.execute(f"ALTER TABLE hospitals ADD COLUMN {col} {definition}")
    
    conn.commit()
    conn.close()
    print("✓ Missing columns added safely")

def setup():
    # DO NOT remove lifeline.db as it contains real data
    # if os.path.exists(DB_PATH):
    #     os.remove(DB_PATH)
    
    add_missing_columns()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Re-verify tables exist (in case someone deleted the file manually)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS hospitals (
        id TEXT PRIMARY KEY, 
        name TEXT, 
        city TEXT,
        address TEXT, 
        contact_number TEXT,
        lat REAL, 
        lng REAL, 
        hospital_type TEXT DEFAULT 'Public',
        status TEXT DEFAULT 'active'
    );
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, 
        email TEXT UNIQUE,
        password TEXT, 
        full_name TEXT,
        role TEXT, 
        hospital_id TEXT,
        phone_number TEXT DEFAULT '',
        employee_id TEXT DEFAULT '',
        department TEXT DEFAULT 'Blood Bank',
        shift TEXT DEFAULT 'Morning',
        is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS donors (
        id TEXT PRIMARY KEY, cnic TEXT UNIQUE,
        full_name TEXT, blood_group TEXT, age INTEGER,
        last_donation_date TEXT, on_blood_thinners INTEGER DEFAULT 0,
        risk_score INTEGER DEFAULT 100, diseases TEXT DEFAULT '',
        screening_hiv TEXT DEFAULT 'passed',
        screening_hepb TEXT DEFAULT 'passed',
        screening_hepc TEXT DEFAULT 'passed',
        screening_syphilis TEXT DEFAULT 'passed',
        screening_malaria TEXT DEFAULT 'passed',
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS patients (
        id TEXT PRIMARY KEY, hospital_id TEXT,
        cnic TEXT, full_name TEXT, father_name TEXT,
        age INTEGER, gender TEXT, blood_group TEXT, mrn TEXT,
        ward TEXT, bed TEXT, opd_number TEXT, diagnosis TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS blood_units (
        id TEXT PRIMARY KEY, hospital_id TEXT,
        donor_id TEXT, blood_group TEXT, component TEXT,
        volume_ml INTEGER, collection_date TEXT,
        expiry_date TEXT, storage_temperature REAL,
        status TEXT DEFAULT 'available'
    );
    CREATE TABLE IF NOT EXISTS contracts (
        id TEXT PRIMARY KEY, ticket_id TEXT UNIQUE,
        lending_hospital_id TEXT, borrowing_hospital_id TEXT,
        patient_id TEXT, blood_unit_id TEXT,
        blood_group TEXT, component TEXT, units INTEGER DEFAULT 1,
        issue_time TEXT, return_deadline TEXT,
        status TEXT DEFAULT 'active',
        is_exchange INTEGER DEFAULT 0, is_returned INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS exchange_offers (
        id TEXT PRIMARY KEY, offering_hospital_id TEXT,
        receiving_hospital_id TEXT, offered_blood_group TEXT,
        requested_blood_group TEXT, units INTEGER, status TEXT
    );
    CREATE TABLE IF NOT EXISTS emergency_requests (
        id TEXT PRIMARY KEY, requesting_hospital_id TEXT,
        target_hospital_id TEXT, blood_group TEXT,
        component TEXT, units_required INTEGER,
        urgency_level TEXT, status TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY, action TEXT, actor_id TEXT,
        hospital_id TEXT, entity_type TEXT, entity_id TEXT,
        details TEXT, previous_hash TEXT, current_hash TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS transfusion_records (
        id TEXT PRIMARY KEY, patient_id TEXT,
        unit_id TEXT, hospital_id TEXT,
        pre_bp_sys INTEGER, pre_bp_dia INTEGER,
        pre_pulse INTEGER, pre_temp REAL, pre_o2 INTEGER,
        post_bp_sys INTEGER, post_bp_dia INTEGER,
        post_pulse INTEGER, post_temp REAL, post_o2 INTEGER,
        reaction_type TEXT DEFAULT 'none',
        action_taken TEXT, nurse_name TEXT,
        start_time TEXT, end_time TEXT
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY, hospital_id TEXT,
        type TEXT, title TEXT, message TEXT,
        is_read INTEGER DEFAULT 0, created_at TEXT
    );
    """)

    # --- Hospitals (Fixing coordinates) ---
    hospitals = [
        ('Mayo Hospital',      'Lahore', 'Hospital Road, Lahore',        '042-99211129', 31.5734, 74.3044, 'Public', 'active'),
        ('Shaukat Khanum Memorial Cancer Hospital',     'Lahore', '7A Block R-3, Johar Town',     '042-35905000', 31.4619, 74.2704, 'Private', 'active'),
        ('Services Hospital',  'Lahore', 'Jail Road, Lahore',             '042-99203402', 31.5497, 74.3436, 'Teaching', 'active'),
        ('Jinnah Hospital',    'Lahore', 'Jail Road, Lahore',             '042-99231400', 31.5204, 74.3587, 'Public', 'active'),
    ]
    
    for h in hospitals:
        # Update if exists, otherwise insert (using name as key for simplicity in seeding)
        c.execute("SELECT id FROM hospitals WHERE name = ?", (h[0],))
        row = c.fetchone()
        if row:
            c.execute("""UPDATE hospitals SET city=?, address=?, contact_number=?, lat=?, lng=?, hospital_type=?, status=? 
                         WHERE id=?""", (h[1], h[2], h[3], h[4], h[5], h[6], h[7], row[0]))
        else:
            hid = str(uuid.uuid4())
            c.execute("""INSERT INTO hospitals (id,name,city,address,contact_number,lat,lng,hospital_type,status) 
                         VALUES (?,?,?,?,?,?,?,?,?)""", (hid, h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7]))

    # --- Users ---
    pwd = hash_password("lifeline123")
    # Using email as key to avoid duplicates
    admin_users = [
        ('admin@lifeline.com',    pwd, 'Super Admin',      'super_admin',    None, '0300-1234567', 'EMP-001', 'Admin', 'Morning', 1),
    ]
    for u in admin_users:
        c.execute("SELECT id FROM users WHERE email = ?", (u[0],))
        if not c.fetchone():
            uid = str(uuid.uuid4())
            c.execute("""INSERT INTO users (id,email,password,full_name,role,hospital_id,phone_number,employee_id,department,shift,is_active) 
                         VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (uid, u[0], u[1], u[2], u[3], u[4], u[5], u[6], u[7], u[8], u[9]))

    conn.commit()
    conn.close()
    print("=" * 50)
    print(" LIFELINE Database Updated Successfully!")
    print("=" * 50)

if __name__ == "__main__":
    setup()
