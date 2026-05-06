import sqlite3
import uuid
import hashlib
import os
from datetime import datetime, timedelta

DB_PATH = "lifeline.db"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def setup():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE hospitals (
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
    CREATE TABLE users (
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
    CREATE TABLE donors (
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
    CREATE TABLE patients (
        id TEXT PRIMARY KEY, hospital_id TEXT,
        cnic TEXT, full_name TEXT, father_name TEXT,
        age INTEGER, gender TEXT, blood_group TEXT, mrn TEXT,
        ward TEXT, bed TEXT, opd_number TEXT, diagnosis TEXT,
        created_at TEXT
    );
    CREATE TABLE blood_units (
        id TEXT PRIMARY KEY, hospital_id TEXT,
        donor_id TEXT, blood_group TEXT, component TEXT,
        volume_ml INTEGER, collection_date TEXT,
        expiry_date TEXT, storage_temperature REAL,
        status TEXT DEFAULT 'available'
    );
    CREATE TABLE contracts (
        id TEXT PRIMARY KEY, ticket_id TEXT UNIQUE,
        lending_hospital_id TEXT, borrowing_hospital_id TEXT,
        patient_id TEXT, blood_unit_id TEXT,
        blood_group TEXT, component TEXT, units INTEGER DEFAULT 1,
        issue_time TEXT, return_deadline TEXT,
        status TEXT DEFAULT 'active',
        is_exchange INTEGER DEFAULT 0, is_returned INTEGER DEFAULT 0
    );
    CREATE TABLE exchange_offers (
        id TEXT PRIMARY KEY, offering_hospital_id TEXT,
        receiving_hospital_id TEXT, offered_blood_group TEXT,
        requested_blood_group TEXT, units INTEGER, status TEXT
    );
    CREATE TABLE emergency_requests (
        id TEXT PRIMARY KEY, requesting_hospital_id TEXT,
        target_hospital_id TEXT, blood_group TEXT,
        component TEXT, units_required INTEGER,
        urgency_level TEXT, status TEXT, created_at TEXT
    );
    CREATE TABLE audit_logs (
        id TEXT PRIMARY KEY, action TEXT, actor_id TEXT,
        hospital_id TEXT, entity_type TEXT, entity_id TEXT,
        details TEXT, previous_hash TEXT, current_hash TEXT,
        created_at TEXT
    );
    CREATE TABLE transfusion_records (
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
    CREATE TABLE notifications (
        id TEXT PRIMARY KEY, hospital_id TEXT,
        type TEXT, title TEXT, message TEXT,
        is_read INTEGER DEFAULT 0, created_at TEXT
    );
    """)

    # --- Hospitals ---
    hospitals = [
        (str(uuid.uuid4()), 'Mayo Hospital',      'Lahore', 'Hospital Road, Lahore',        '042-99211129', 31.5734, 74.3044, 'Public', 'active'),
        (str(uuid.uuid4()), 'Shaukat Khanum',     'Lahore', '7A Block R-3, Johar Town',     '042-35905000', 31.4619, 74.2704, 'Private', 'active'),
        (str(uuid.uuid4()), 'Services Hospital',  'Lahore', 'Jail Road, Lahore',             '042-99203402', 31.5497, 74.3436, 'Teaching', 'active'),
        (str(uuid.uuid4()), 'Jinnah Hospital',    'Lahore', 'Jail Road, Lahore',             '042-99231400', 31.5204, 74.3587, 'Public', 'active'),
    ]
    c.executemany("INSERT INTO hospitals (id,name,city,address,contact_number,lat,lng,hospital_type,status) VALUES (?,?,?,?,?,?,?,?,?)", hospitals)
    h1,h2,h3,h4 = [r[0] for r in hospitals]

    # --- Users (sha256 hashed) ---
    pwd = hash_password("lifeline123")
    users = [
        # id, email, password, full_name, role, hospital_id, phone, emp_id, dept, shift, is_active
        (str(uuid.uuid4()), 'admin@lifeline.com',    pwd, 'Super Admin',      'super_admin',    None, '0300-1234567', 'EMP-001', 'Admin', 'Morning', 1),
        (str(uuid.uuid4()), 'mayo@lifeline.com',     pwd, 'Dr. Arif Hussain', 'hospital_admin', h1, '0300-1112223', 'EMP-101', 'Blood Bank', 'Morning', 1),
        (str(uuid.uuid4()), 'services@lifeline.com', pwd, 'Dr. Sara Malik',   'hospital_admin', h3, '0300-4445556', 'EMP-301', 'Blood Bank', 'Morning', 1),
        (str(uuid.uuid4()), 'staff@lifeline.com',    pwd, 'Nurse Aisha',      'staff',          h1, '0312-9876543', 'EMP-102', 'Lab', 'Morning', 1),
        (str(uuid.uuid4()), 'hosp2@lifeline.com',    pwd, 'Dr. Kamran Ahmed', 'hospital_admin', h2, '0321-5556667', 'EMP-201', 'Blood Bank', 'Evening', 1),
        (str(uuid.uuid4()), 'hosp4@lifeline.com',    pwd, 'Dr. Fatima Noor',  'hospital_admin', h4, '0333-8889990', 'EMP-401', 'Blood Bank', 'Night', 1),
        (str(uuid.uuid4()), 'worker1@lifeline.com',  pwd, 'Ali Hassan',       'staff',          h3, '0345-0001112', 'EMP-302', 'Emergency', 'Night', 1),
    ]
    c.executemany("INSERT INTO users (id,email,password,full_name,role,hospital_id,phone_number,employee_id,department,shift,is_active) VALUES (?,?,?,?,?,?,?,?,?,?,?)", users)

    # --- Donors ---
    now_str = datetime.now().isoformat()
    donors = [
        (str(uuid.uuid4()), '35202-1111111-1', 'Muhammad Ali Khan',   'O+',  28, '2024-11-01', 0, 95, '',          'passed','passed','passed','passed','passed', now_str),
        (str(uuid.uuid4()), '35202-2222222-2', 'Fahad Bilal',         'A+',  34, '2024-08-15', 0, 88, '',          'passed','passed','passed','passed','passed', now_str),
        (str(uuid.uuid4()), '35202-3333333-3', 'Omar Tariq',          'B+',  45, '2024-06-20', 0, 72, 'Diabetes', 'passed','passed','passed','passed','passed', now_str),
        (str(uuid.uuid4()), '35202-4444444-4', 'Zohaib Raza',         'AB+', 29, '2025-01-10', 0, 82, '',          'passed','passed','passed','passed','passed', now_str),
        (str(uuid.uuid4()), '35202-5555555-5', 'Hassan Mehmood',      'O-',  55, '2023-12-01', 1, 58, 'Hypertension','passed','passed','passed','passed','passed',now_str),
        (str(uuid.uuid4()), '35202-6666666-6', 'Salman Tariq',        'A-',  31, '2024-09-05', 0, 91, '',          'passed','passed','passed','passed','passed', now_str),
        (str(uuid.uuid4()), '35202-7777777-7', 'Bilal Ahmed',         'B-',  40, '2024-07-18', 0, 65, 'Diabetes,Hypertension','passed','passed','passed','passed','passed',now_str),
        (str(uuid.uuid4()), '35202-8888888-8', 'Kamran Akmal',        'AB-', 38, '2024-04-12', 0, 10, 'Hepatitis B','passed','failed','passed','passed','passed', now_str),
    ]
    c.executemany("""INSERT INTO donors (id,cnic,full_name,blood_group,age,last_donation_date,
        on_blood_thinners,risk_score,diseases,screening_hiv,screening_hepb,screening_hepc,
        screening_syphilis,screening_malaria,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", donors)
    d1,d2,d3,d4,d5,d6,d7,d8 = [r[0] for r in donors]

    # --- Patients ---
    patients = [
        (str(uuid.uuid4()), h4, '35202-6848357-8', 'Aamir Hussain', 'Usman Shah', 27, 'Male', 'A+', 'MRN-1000', 'Surgical', 'Bed-15', 'OPD-2000', 'Post-operative haemorrhage', now_str),
        (str(uuid.uuid4()), h4, '35202-4266882-1', 'Farhan Qureshi', 'Rizwan Hussain', 42, 'Male', 'O+', 'MRN-1001', 'Orthopaedics', 'Bed-14', 'OPD-2001', 'Gastrointestinal bleeding', now_str),
        (str(uuid.uuid4()), h1, '35202-6985053-8', 'Kamran Shah', 'Rehan Ahmed', 64, 'Male', 'AB+', 'MRN-1002', 'General', 'Bed-19', 'OPD-2002', 'Road traffic accident', now_str),
        (str(uuid.uuid4()), h4, '35202-9056363-8', 'Imran Ahmed', 'Kamran Khan', 60, 'Male', 'A+', 'MRN-1003', 'ICU', 'Bed-1', 'OPD-2003', 'Post-operative haemorrhage', now_str),
        (str(uuid.uuid4()), h1, '35202-6445965-7', 'Ali Iqbal', 'Hassan Mirza', 41, 'Male', 'O+', 'MRN-1004', 'Orthopaedics', 'Bed-13', 'OPD-2004', 'Severe anaemia', now_str),
        (str(uuid.uuid4()), h3, '35202-8779638-5', 'Faisal Qureshi', 'Omar Chaudhry', 36, 'Male', 'AB-', 'MRN-1005', 'General', 'Bed-5', 'OPD-2005', 'Burn trauma', now_str),
    ]
    c.executemany("""INSERT INTO patients (id,hospital_id,cnic,full_name,father_name,age,gender,
        blood_group,mrn,ward,bed,opd_number,diagnosis,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", patients)
    p1,p2,p3,p4,p5,p6 = [r[0] for r in patients[:6]]

    # --- Blood Units (20 total) ---
    today = datetime.now().date()
    units_data = [
        (str(uuid.uuid4()), h1, d1, 'O+',  'Whole Blood', 450, '2026-04-01', str(today + timedelta(days=2)),  4.0),
        (str(uuid.uuid4()), h2, d2, 'A+',  'RBC',         300, '2026-04-05', str(today + timedelta(days=2)),  4.0),
        (str(uuid.uuid4()), h3, d3, 'B+',  'Platelets',   200, '2026-04-08', str(today + timedelta(days=1)),  22.0),
        (str(uuid.uuid4()), h1, d4, 'AB+', 'Plasma',      250, '2026-04-10', str(today + timedelta(days=4)),  -20.0),
        (str(uuid.uuid4()), h2, d5, 'O-',  'Whole Blood', 450, '2026-04-12', str(today + timedelta(days=5)),  4.0),
    ]
    c.executemany("""INSERT INTO blood_units (id,hospital_id,donor_id,blood_group,component,
        volume_ml,collection_date,expiry_date,storage_temperature) VALUES (?,?,?,?,?,?,?,?,?)""", units_data)
    u_ids = [r[0] for r in units_data]

    # --- Contracts ---
    now = datetime.now()
    contracts_data = [
        (str(uuid.uuid4()), 'LF-2026-0001', h2, h1, p1, u_ids[0],  'O+',  'Whole Blood', 2,
         (now - timedelta(hours=20)).isoformat(), (now + timedelta(hours=4)).isoformat(),  'active', 0, 0),
    ]
    c.executemany("""INSERT INTO contracts (id,ticket_id,lending_hospital_id,borrowing_hospital_id,
        patient_id,blood_unit_id,blood_group,component,units,issue_time,return_deadline,status,is_exchange,is_returned)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", contracts_data)

    # --- Audit Logs ---
    logs = [
        (str(uuid.uuid4()), 'SYSTEM_INIT',     'system',          None, 'system',   'db',     '{"msg":"Database initialized"}', 'genesis','hash0', now.isoformat()),
    ]
    c.executemany("""INSERT INTO audit_logs (id,action,actor_id,hospital_id,entity_type,entity_id,
        details,previous_hash,current_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""", logs)

    conn.commit()
    conn.close()
    print("=" * 50)
    print(" LIFELINE Database Initialized Successfully!")
    print("=" * 50)

if __name__ == "__main__":
    setup()
