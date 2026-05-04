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
        id TEXT PRIMARY KEY, name TEXT, city TEXT,
        address TEXT, contact_number TEXT,
        lat REAL, lng REAL, is_active INTEGER DEFAULT 1
    );
    CREATE TABLE users (
        id TEXT PRIMARY KEY, email TEXT UNIQUE,
        password TEXT, full_name TEXT,
        role TEXT, hospital_id TEXT
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
        (str(uuid.uuid4()), 'Mayo Hospital',      'Lahore', 'Hospital Road, Lahore',        '042-99211129', 31.5734, 74.3044),
        (str(uuid.uuid4()), 'Shaukat Khanum',     'Lahore', '7A Block R-3, Johar Town',     '042-35905000', 31.4619, 74.2704),
        (str(uuid.uuid4()), 'Services Hospital',  'Lahore', 'Jail Road, Lahore',             '042-99203402', 31.5497, 74.3436),
        (str(uuid.uuid4()), 'Jinnah Hospital',    'Lahore', 'Jail Road, Lahore',             '042-99231400', 31.5204, 74.3587),
    ]
    c.executemany("INSERT INTO hospitals (id,name,city,address,contact_number,lat,lng) VALUES (?,?,?,?,?,?,?)", hospitals)
    h1,h2,h3,h4 = [r[0] for r in hospitals]

    # --- Users (sha256 hashed) ---
    pwd = hash_password("lifeline123")
    users = [
        (str(uuid.uuid4()), 'admin@lifeline.com',    pwd, 'Super Admin',      'super_admin',    None),
        (str(uuid.uuid4()), 'mayo@lifeline.com',     pwd, 'Dr. Arif Hussain', 'hospital_admin', h1),
        (str(uuid.uuid4()), 'services@lifeline.com', pwd, 'Dr. Sara Malik',   'hospital_admin', h3),
        (str(uuid.uuid4()), 'staff@lifeline.com',    pwd, 'Nurse Aisha',      'staff',          h1),
        (str(uuid.uuid4()), 'hosp2@lifeline.com',    pwd, 'Dr. Kamran Ahmed', 'hospital_admin', h2),
        (str(uuid.uuid4()), 'hosp4@lifeline.com',    pwd, 'Dr. Fatima Noor',  'hospital_admin', h4),
        (str(uuid.uuid4()), 'worker1@lifeline.com',  pwd, 'Ali Hassan',       'staff',          h3),
    ]
    c.executemany("INSERT INTO users (id,email,password,full_name,role,hospital_id) VALUES (?,?,?,?,?,?)", users)

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
        (str(uuid.uuid4()), h4, '35202-5268925-7', 'Salman Qureshi', 'Ahmed Iqbal', 30, 'Male', 'O-', 'MRN-1006', 'Orthopaedics', 'Bed-18', 'OPD-2006', 'Elective cardiac surgery', now_str),
        (str(uuid.uuid4()), h1, '35202-8424130-3', 'Salman Chaudhry', 'Omar Mirza', 32, 'Male', 'B+', 'MRN-1007', 'General', 'Bed-2', 'OPD-2007', 'Elective cardiac surgery', now_str),
        (str(uuid.uuid4()), h1, '35202-7668099-8', 'Usman Ahmed', 'Salman Farooq', 58, 'Male', 'B-', 'MRN-1008', 'Orthopaedics', 'Bed-15', 'OPD-2008', 'Burn trauma', now_str),
        (str(uuid.uuid4()), h4, '35202-9137097-3', 'Junaid Chaudhry', 'Rehan Mehmood', 33, 'Male', 'B+', 'MRN-1009', 'Orthopaedics', 'Bed-17', 'OPD-2009', 'Road traffic accident', now_str),
        (str(uuid.uuid4()), h1, '35202-2238588-1', 'Rehan Malik', 'Junaid Tariq', 22, 'Male', 'A+', 'MRN-1010', 'Cardiology', 'Bed-16', 'OPD-2010', 'Orthopaedic surgery', now_str),
        (str(uuid.uuid4()), h1, '35202-3432068-7', 'Faisal Malik', 'Nabeel Siddiqui', 53, 'Male', 'A-', 'MRN-1011', 'Surgical', 'Bed-14', 'OPD-2011', 'Severe anaemia', now_str),
        (str(uuid.uuid4()), h1, '35202-9219542-2', 'Hassan Hussain', 'Ahmed Malik', 67, 'Male', 'B+', 'MRN-1012', 'Emergency', 'Bed-19', 'OPD-2012', 'Gastrointestinal bleeding', now_str),
        (str(uuid.uuid4()), h3, '35202-1349913-9', 'Junaid Qureshi', 'Bilal Shah', 64, 'Male', 'O-', 'MRN-1013', 'Orthopaedics', 'Bed-9', 'OPD-2013', 'Severe anaemia', now_str),
        (str(uuid.uuid4()), h1, '35202-8719677-2', 'Faisal Malik', 'Rizwan Siddiqui', 44, 'Male', 'A+', 'MRN-1014', 'Emergency', 'Bed-3', 'OPD-2014', 'Elective cardiac surgery', now_str),
        (str(uuid.uuid4()), h3, '35202-9390507-2', 'Faisal Mirza', 'Aamir Mirza', 36, 'Male', 'AB+', 'MRN-1015', 'Orthopaedics', 'Bed-18', 'OPD-2015', 'Road traffic accident', now_str),
        (str(uuid.uuid4()), h3, '35202-5686759-4', 'Bilal Farooq', 'Kamran Raza', 31, 'Male', 'O-', 'MRN-1016', 'Cardiology', 'Bed-16', 'OPD-2016', 'Post-operative haemorrhage', now_str),
        (str(uuid.uuid4()), h3, '35202-1831148-2', 'Faisal Farooq', 'Farhan Farooq', 65, 'Male', 'A-', 'MRN-1017', 'General', 'Bed-15', 'OPD-2017', 'Gastrointestinal bleeding', now_str),
        (str(uuid.uuid4()), h1, '35202-8648077-1', 'Saad Farooq', 'Rehan Ahmed', 64, 'Male', 'B-', 'MRN-1018', 'General', 'Bed-13', 'OPD-2018', 'Dengue fever', now_str),
        (str(uuid.uuid4()), h4, '35202-8200406-1', 'Bilal Mirza', 'Rizwan Farooq', 51, 'Male', 'O-', 'MRN-1019', 'ICU', 'Bed-1', 'OPD-2019', 'Elective cardiac surgery', now_str),
        (str(uuid.uuid4()), h3, '35202-4132848-2', 'Kashif Shah', 'Omar Khan', 50, 'Male', 'AB-', 'MRN-1020', 'General', 'Bed-6', 'OPD-2020', 'Road traffic accident', now_str),
        (str(uuid.uuid4()), h3, '35202-6360572-2', 'Tariq Qureshi', 'Kamran Farooq', 47, 'Male', 'B+', 'MRN-1021', 'General', 'Bed-15', 'OPD-2021', 'Thalassaemia transfusion', now_str),
        (str(uuid.uuid4()), h1, '35202-2812253-7', 'Zain Raza', 'Ahmed Hussain', 68, 'Male', 'AB+', 'MRN-1022', 'Emergency', 'Bed-10', 'OPD-2022', 'Elective cardiac surgery', now_str),
        (str(uuid.uuid4()), h4, '35202-1735672-3', 'Tariq Siddiqui', 'Junaid Shah', 63, 'Male', 'O-', 'MRN-1023', 'Surgical', 'Bed-19', 'OPD-2023', 'Burn trauma', now_str),
        (str(uuid.uuid4()), h1, '35202-8517610-5', 'Ahmed Shah', 'Bilal Ali', 26, 'Male', 'A+', 'MRN-1024', 'Cardiology', 'Bed-10', 'OPD-2024', 'Gastrointestinal bleeding', now_str),
        (str(uuid.uuid4()), h1, '35202-8027072-4', 'Kamran Raza', 'Faisal Tariq', 67, 'Male', 'AB+', 'MRN-1025', 'Emergency', 'Bed-12', 'OPD-2025', 'Thalassaemia transfusion', now_str),
        (str(uuid.uuid4()), h3, '35202-7935393-4', 'Nabeel Siddiqui', 'Shahzad Farooq', 33, 'Male', 'A+', 'MRN-1026', 'Cardiology', 'Bed-7', 'OPD-2026', 'Road traffic accident', now_str),
        (str(uuid.uuid4()), h2, '35202-8837978-8', 'Hassan Malik', 'Bilal Shah', 21, 'Male', 'AB-', 'MRN-1027', 'Orthopaedics', 'Bed-4', 'OPD-2027', 'Post-operative haemorrhage', now_str),
        (str(uuid.uuid4()), h3, '35202-8023080-4', 'Faisal Raza', 'Ahmed Farooq', 34, 'Male', 'A+', 'MRN-1028', 'Cardiology', 'Bed-16', 'OPD-2028', 'Dengue fever', now_str),
        (str(uuid.uuid4()), h4, '35202-1650422-4', 'Tariq Iqbal', 'Usman Siddiqui', 23, 'Male', 'A+', 'MRN-1029', 'General', 'Bed-20', 'OPD-2029', 'Burn trauma', now_str),
        (str(uuid.uuid4()), h4, '35202-7982409-5', 'Zain Chaudhry', 'Adnan Raza', 35, 'Male', 'B+', 'MRN-1030', 'Cardiology', 'Bed-6', 'OPD-2030', 'Gastrointestinal bleeding', now_str),
        (str(uuid.uuid4()), h1, '35202-2235064-3', 'Rehan Iqbal', 'Rehan Malik', 30, 'Male', 'AB+', 'MRN-1031', 'Emergency', 'Bed-18', 'OPD-2031', 'Elective cardiac surgery', now_str),
        (str(uuid.uuid4()), h3, '35202-6361780-4', 'Zain Iqbal', 'Junaid Iqbal', 48, 'Male', 'AB-', 'MRN-1032', 'ICU', 'Bed-13', 'OPD-2032', 'Burn trauma', now_str),
        (str(uuid.uuid4()), h2, '35202-2537831-7', 'Rizwan Khan', 'Salman Chaudhry', 57, 'Male', 'B-', 'MRN-1033', 'Surgical', 'Bed-10', 'OPD-2033', 'Dengue fever', now_str),
        (str(uuid.uuid4()), h1, '35202-6689018-4', 'Imran Malik', 'Ahmed Chaudhry', 33, 'Male', 'AB+', 'MRN-1034', 'General', 'Bed-19', 'OPD-2034', 'Burn trauma', now_str),
        (str(uuid.uuid4()), h2, '35202-8481098-5', 'Tariq Mehmood', 'Usman Mirza', 62, 'Male', 'AB-', 'MRN-1035', 'Cardiology', 'Bed-6', 'OPD-2035', 'Orthopaedic surgery', now_str),
        (str(uuid.uuid4()), h1, '35202-4907686-8', 'Faisal Raza', 'Bilal Chaudhry', 49, 'Male', 'O-', 'MRN-1036', 'Orthopaedics', 'Bed-1', 'OPD-2036', 'Thalassaemia transfusion', now_str),
        (str(uuid.uuid4()), h2, '35202-5688325-2', 'Zain Ali', 'Faisal Mehmood', 19, 'Male', 'A-', 'MRN-1037', 'General', 'Bed-10', 'OPD-2037', 'Gastrointestinal bleeding', now_str),
        (str(uuid.uuid4()), h4, '35202-4288964-4', 'Shahzad Siddiqui', 'Hamza Ahmed', 54, 'Male', 'A+', 'MRN-1038', 'Cardiology', 'Bed-15', 'OPD-2038', 'Burn trauma', now_str),
        (str(uuid.uuid4()), h4, '35202-6866344-9', 'Imran Raza', 'Bilal Chaudhry', 31, 'Male', 'O-', 'MRN-1039', 'Cardiology', 'Bed-14', 'OPD-2039', 'Post-operative haemorrhage', now_str),
        (str(uuid.uuid4()), h2, '35202-2843452-5', 'Shahzad Iqbal', 'Adnan Khan', 49, 'Male', 'B+', 'MRN-1040', 'General', 'Bed-9', 'OPD-2040', 'Orthopaedic surgery', now_str),
        (str(uuid.uuid4()), h4, '35202-8203125-1', 'Rehan Ahmed', 'Hassan Qureshi', 44, 'Male', 'B+', 'MRN-1041', 'General', 'Bed-19', 'OPD-2041', 'Elective cardiac surgery', now_str),
        (str(uuid.uuid4()), h2, '35202-6824286-9', 'Rizwan Tariq', 'Saad Chaudhry', 28, 'Male', 'B-', 'MRN-1042', 'Emergency', 'Bed-1', 'OPD-2042', 'Dengue fever', now_str),
        (str(uuid.uuid4()), h4, '35202-9053388-9', 'Tariq Hussain', 'Kashif Malik', 23, 'Male', 'A-', 'MRN-1043', 'Orthopaedics', 'Bed-2', 'OPD-2043', 'Thalassaemia transfusion', now_str),
        (str(uuid.uuid4()), h3, '35202-9076671-9', 'Hamza Hussain', 'Kashif Farooq', 40, 'Male', 'B-', 'MRN-1044', 'Cardiology', 'Bed-12', 'OPD-2044', 'Orthopaedic surgery', now_str),
        (str(uuid.uuid4()), h2, '35202-4111151-8', 'Saad Farooq', 'Kamran Tariq', 66, 'Male', 'B-', 'MRN-1045', 'Orthopaedics', 'Bed-5', 'OPD-2045', 'Thalassaemia transfusion', now_str),
        (str(uuid.uuid4()), h2, '35202-2841010-5', 'Shahzad Ali', 'Rehan Iqbal', 18, 'Male', 'A+', 'MRN-1046', 'Cardiology', 'Bed-5', 'OPD-2046', 'Post-operative haemorrhage', now_str),
        (str(uuid.uuid4()), h3, '35202-8475541-1', 'Shahzad Shah', 'Faisal Ali', 32, 'Male', 'A+', 'MRN-1047', 'General', 'Bed-3', 'OPD-2047', 'Burn trauma', now_str),
        (str(uuid.uuid4()), h3, '35202-1762181-1', 'Rizwan Chaudhry', 'Tariq Siddiqui', 62, 'Male', 'B-', 'MRN-1048', 'Surgical', 'Bed-6', 'OPD-2048', 'Dengue fever', now_str),
        (str(uuid.uuid4()), h3, '35202-8692660-5', 'Bilal Raza', 'Rehan Chaudhry', 65, 'Male', 'B-', 'MRN-1049', 'General', 'Bed-12', 'OPD-2049', 'Orthopaedic surgery', now_str),
    ]
    c.executemany("""INSERT INTO patients (id,hospital_id,cnic,full_name,father_name,age,gender,
        blood_group,mrn,ward,bed,opd_number,diagnosis,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", patients)
    p1,p2,p3,p4,p5,p6 = [r[0] for r in patients[:6]]

    # --- Blood Units (20 total) ---
    today = datetime.now().date()
    units_data = [
        # 3 expiring in 2 days
        (str(uuid.uuid4()), h1, d1, 'O+',  'Whole Blood', 450, '2026-04-01', str(today + timedelta(days=2)),  4.0),
        (str(uuid.uuid4()), h2, d2, 'A+',  'RBC',         300, '2026-04-05', str(today + timedelta(days=2)),  4.0),
        (str(uuid.uuid4()), h3, d3, 'B+',  'Platelets',   200, '2026-04-08', str(today + timedelta(days=1)),  22.0),
        # 5 expiring in 5 days
        (str(uuid.uuid4()), h1, d4, 'AB+', 'Plasma',      250, '2026-04-10', str(today + timedelta(days=4)),  -20.0),
        (str(uuid.uuid4()), h2, d5, 'O-',  'Whole Blood', 450, '2026-04-12', str(today + timedelta(days=5)),  4.0),
        (str(uuid.uuid4()), h3, d6, 'A-',  'RBC',         300, '2026-04-14', str(today + timedelta(days=5)),  4.0),
        (str(uuid.uuid4()), h4, d7, 'B-',  'Platelets',   200, '2026-04-15', str(today + timedelta(days=4)),  22.0),
        (str(uuid.uuid4()), h1, d1, 'O+',  'FFP',         250, '2026-04-16', str(today + timedelta(days=5)),  -30.0),
        # 2 with temp breach (7°C)
        (str(uuid.uuid4()), h2, d2, 'A+',  'Whole Blood', 450, '2026-03-01', str(today + timedelta(days=60)), 7.0),
        (str(uuid.uuid4()), h3, d3, 'B+',  'RBC',         300, '2026-03-05', str(today + timedelta(days=90)), 7.5),
        # 10 safe units expiring 2026
        (str(uuid.uuid4()), h1, d4, 'AB+', 'Whole Blood', 450, '2026-01-01', '2026-12-01', 4.0),
        (str(uuid.uuid4()), h2, d5, 'O-',  'RBC',         300, '2026-01-05', '2026-11-15', 4.0),
        (str(uuid.uuid4()), h3, d6, 'A-',  'Platelets',   200, '2026-01-10', '2026-10-20', 22.0),
        (str(uuid.uuid4()), h4, d7, 'B-',  'Plasma',      250, '2026-01-12', '2026-12-10', -20.0),
        (str(uuid.uuid4()), h1, d1, 'O+',  'Whole Blood', 450, '2026-02-01', '2026-11-01', 4.0),
        (str(uuid.uuid4()), h2, d2, 'A+',  'RBC',         300, '2026-02-05', '2026-10-15', 4.0),
        (str(uuid.uuid4()), h3, d3, 'B+',  'Platelets',   200, '2026-02-10', '2026-09-20', 22.0),
        (str(uuid.uuid4()), h4, d4, 'AB-', 'Plasma',      250, '2026-02-12', '2026-12-05', -20.0),
        (str(uuid.uuid4()), h1, d5, 'O-',  'FFP',         250, '2026-03-01', '2026-11-30', -30.0),
        (str(uuid.uuid4()), h2, d6, 'A-',  'Whole Blood', 450, '2026-03-05', '2026-10-25', 4.0),
    ]
    c.executemany("""INSERT INTO blood_units (id,hospital_id,donor_id,blood_group,component,
        volume_ml,collection_date,expiry_date,storage_temperature) VALUES (?,?,?,?,?,?,?,?,?)""", units_data)
    u_ids = [r[0] for r in units_data]

    # --- Contracts (3: critical, warning, safe) ---
    now = datetime.now()
    contracts_data = [
        (str(uuid.uuid4()), 'LF-2026-0001', h2, h1, p1, u_ids[0],  'O+',  'Whole Blood', 2,
         (now - timedelta(hours=20)).isoformat(), (now + timedelta(hours=4)).isoformat(),  'active', 0, 0),
        (str(uuid.uuid4()), 'LF-2026-0002', h3, h2, p2, u_ids[1],  'A+',  'RBC',         1,
         (now - timedelta(hours=14)).isoformat(), (now + timedelta(hours=10)).isoformat(), 'active', 0, 0),
        (str(uuid.uuid4()), 'LF-2026-0003', h4, h3, p3, u_ids[2],  'B+',  'Platelets',   3,
         (now - timedelta(hours=4)).isoformat(),  (now + timedelta(hours=20)).isoformat(), 'active', 0, 0),
    ]
    c.executemany("""INSERT INTO contracts (id,ticket_id,lending_hospital_id,borrowing_hospital_id,
        patient_id,blood_unit_id,blood_group,component,units,issue_time,return_deadline,status,is_exchange,is_returned)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", contracts_data)

    # --- Exchange Offers (perfect match: Mayo has A+, needs B+; Services has B+, needs A+) ---
    exchange_data = [
        (str(uuid.uuid4()), h1, None, 'A+', 'B+', 2, 'pending'),
        (str(uuid.uuid4()), h3, None, 'B+', 'A+', 2, 'pending'),
    ]
    c.executemany("""INSERT INTO exchange_offers (id,offering_hospital_id,receiving_hospital_id,
        offered_blood_group,requested_blood_group,units,status) VALUES (?,?,?,?,?,?,?)""", exchange_data)

    # --- Emergency Requests ---
    emg_data = [
        (str(uuid.uuid4()), h2, h1, 'O-', 'Whole Blood', 2, 'Level 1 - Critical', 'pending',
         (now - timedelta(minutes=15)).isoformat()),
        (str(uuid.uuid4()), h4, h3, 'AB-','Plasma',       1, 'Level 2 - Urgent',   'pending',
         (now - timedelta(hours=1)).isoformat()),
    ]
    c.executemany("""INSERT INTO emergency_requests (id,requesting_hospital_id,target_hospital_id,
        blood_group,component,units_required,urgency_level,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)""", emg_data)

    # --- Seed a few audit logs ---
    logs = [
        (str(uuid.uuid4()), 'SYSTEM_INIT',     'system',          None, 'system',   'db',     '{"msg":"Database initialized"}', 'genesis','hash0', now.isoformat()),
        (str(uuid.uuid4()), 'USER_LOGIN',      'admin@lifeline.com', None,'user',   'admin',  '{"msg":"Admin logged in"}',      'hash0',  'hash1', (now-timedelta(minutes=5)).isoformat()),
        (str(uuid.uuid4()), 'UNIT_REGISTERED', 'mayo@lifeline.com',  h1,  'unit',   u_ids[0], '{"blood_group":"O+"}',           'hash1',  'hash2', (now-timedelta(minutes=3)).isoformat()),
        (str(uuid.uuid4()), 'CONTRACT_CREATED','admin@lifeline.com', h1,  'contract','LF-2026-0001','{"ticket":"LF-2026-0001"}','hash2',  'hash3', (now-timedelta(minutes=2)).isoformat()),
    ]
    c.executemany("""INSERT INTO audit_logs (id,action,actor_id,hospital_id,entity_type,entity_id,
        details,previous_hash,current_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""", logs)

    # --- Notifications ---
    notifications = [
        (str(uuid.uuid4()), h1, 'info', 'System Update', 'Lifeline v5.0 deployed successfully.', 0, now.isoformat()),
        (str(uuid.uuid4()), h1, 'warning', 'Low Stock', 'O- inventory is running low.', 0, (now - timedelta(minutes=30)).isoformat()),
        (str(uuid.uuid4()), h1, 'critical', 'Contract Breach', 'Ticket LF-2026-0001 is nearing its deadline.', 0, (now - timedelta(hours=1)).isoformat()),
    ]
    c.executemany("""INSERT INTO notifications (id,hospital_id,type,title,message,is_read,created_at)
        VALUES (?,?,?,?,?,?,?)""", notifications)

    conn.commit()
    conn.close()
    print("=" * 50)
    print(" LIFELINE Database Initialized Successfully!")
    print("=" * 50)
    print(f"  Hospitals : 4")
    print(f"  Users     : 7")
    print(f"  Donors    : 8")
    print(f"  Patients  : {len(patients)}")
    print(f"  Units     : 20")
    print(f"  Contracts : 3")
    print(f"  Exchanges : 2")
    print(f"  Emergencies: 2")
    print("=" * 50)
    print("  Login: admin@lifeline.com / lifeline123")
    print("         mayo@lifeline.com  / lifeline123")
    print("         staff@lifeline.com / lifeline123")
    print("=" * 50)

if __name__ == "__main__":
    setup()
