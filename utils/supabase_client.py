import sqlite3
import uuid
import json
import hashlib
from datetime import datetime, timedelta

DB_PATH = "lifeline.db"

# ─────────────────────────────────────────────
# CORE HELPERS
# ─────────────────────────────────────────────

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _q(sql, params=()):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(sql, params)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"Query Error: {e}")
        return []

def _x(sql, params=()):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(sql, params)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Execute Error: {e}")
        return False

def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def init_db():
    """Initialize schema if tables don't exist."""
    conn = get_connection()
    c = conn.cursor()
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
        id TEXT PRIMARY KEY, cnic TEXT UNIQUE, full_name TEXT,
        blood_group TEXT, age INTEGER, last_donation_date TEXT,
        on_blood_thinners INTEGER DEFAULT 0, risk_score INTEGER DEFAULT 100,
        diseases TEXT DEFAULT '',
        screening_hiv TEXT DEFAULT 'passed', screening_hepb TEXT DEFAULT 'passed',
        screening_hepc TEXT DEFAULT 'passed', screening_syphilis TEXT DEFAULT 'passed',
        screening_malaria TEXT DEFAULT 'passed', created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS patients (
        id TEXT PRIMARY KEY, hospital_id TEXT, cnic TEXT, full_name TEXT,
        father_name TEXT, age INTEGER, gender TEXT, blood_group TEXT, mrn TEXT,
        ward TEXT, bed TEXT, opd_number TEXT, diagnosis TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS blood_units (
        id TEXT PRIMARY KEY, hospital_id TEXT, donor_id TEXT, blood_group TEXT,
        component TEXT, volume_ml INTEGER, collection_date TEXT, expiry_date TEXT,
        storage_temperature REAL, status TEXT DEFAULT 'available'
    );
    CREATE TABLE IF NOT EXISTS contracts (
        id TEXT PRIMARY KEY, ticket_id TEXT UNIQUE,
        lending_hospital_id TEXT, borrowing_hospital_id TEXT,
        patient_id TEXT, blood_unit_id TEXT, blood_group TEXT,
        component TEXT, units INTEGER DEFAULT 1, issue_time TEXT,
        return_deadline TEXT, status TEXT DEFAULT 'active',
        is_exchange INTEGER DEFAULT 0, is_returned INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS exchange_offers (
        id TEXT PRIMARY KEY, offering_hospital_id TEXT,
        receiving_hospital_id TEXT, offered_blood_group TEXT,
        requested_blood_group TEXT, units INTEGER, status TEXT
    );
    CREATE TABLE IF NOT EXISTS emergency_requests (
        id TEXT PRIMARY KEY, requesting_hospital_id TEXT,
        target_hospital_id TEXT, blood_group TEXT, component TEXT,
        units_required INTEGER, urgency_level TEXT, status TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY, action TEXT, actor_id TEXT, hospital_id TEXT,
        entity_type TEXT, entity_id TEXT, details TEXT,
        previous_hash TEXT, current_hash TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS transfusion_records (
        id TEXT PRIMARY KEY, patient_id TEXT, unit_id TEXT, hospital_id TEXT,
        pre_bp_sys INTEGER, pre_bp_dia INTEGER, pre_pulse INTEGER,
        pre_temp REAL, pre_o2 INTEGER, post_bp_sys INTEGER, post_bp_dia INTEGER,
        post_pulse INTEGER, post_temp REAL, post_o2 INTEGER,
        reaction_type TEXT DEFAULT 'none', action_taken TEXT,
        nurse_name TEXT, start_time TEXT, end_time TEXT
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY, hospital_id TEXT, type TEXT, title TEXT,
        message TEXT, is_read INTEGER DEFAULT 0, created_at TEXT
    );
    """)
    conn.commit()
    conn.close()

init_db()

# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def auth_login(email: str, password: str):
    hashed = _hash(password)
    rows = _q("""SELECT id, email, role, hospital_id, full_name, 
                 department, shift, employee_id, phone_number, is_active 
                 FROM users WHERE email=? AND password=?""",
              (email, hashed))
    if rows:
        if rows[0]["is_active"] == 0:
            return "DEACTIVATED"
        return dict(rows[0])
    return None

def auth_signup(email, password, full_name, role, hospital_id, **kwargs):
    try:
        uid = str(uuid.uuid4())
        phone = kwargs.get("phone_number", "")
        emp_id = kwargs.get("employee_id", "")
        dept = kwargs.get("department", "Blood Bank")
        shift = kwargs.get("shift", "Morning")
        
        return _x("""INSERT INTO users (id,email,password,full_name,role,hospital_id,
                     phone_number,employee_id,department,shift,is_active) 
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (uid, email, _hash(password), full_name, role, hospital_id,
                   phone, emp_id, dept, shift, 1))
    except Exception as e:
        print(f"Signup Error: {e}")
        return False

def change_password(user_id, current_pass, new_pass):
    hashed_curr = _hash(current_pass)
    user = _q("SELECT id FROM users WHERE id=? AND password=?", (user_id, hashed_curr))
    if not user:
        return False
    hashed_new = _hash(new_pass)
    return _x("UPDATE users SET password = ? WHERE id = ?", (hashed_new, user_id))

# ─────────────────────────────────────────────
# HOSPITALS
# ─────────────────────────────────────────────

def get_hospitals() -> list:
    return _q("SELECT * FROM hospitals ORDER BY name")

def get_hospital_by_id(hid: str) -> dict:
    rows = _q("SELECT * FROM hospitals WHERE id=?", (hid,))
    return rows[0] if rows else {}

def add_hospital(hospital: dict) -> str:
    new_id = str(uuid.uuid4())
    ok = _x("""INSERT INTO hospitals (id, name, city, address, contact_number, 
               lat, lng, hospital_type, status) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (new_id, hospital['name'], hospital.get('city', 'Lahore'), 
             hospital.get('address', ''), hospital.get('contact_number', ''),
             hospital.get('lat', 31.5734), hospital.get('lng', 74.3044),
             hospital.get('hospital_type', 'Public'), hospital.get('status', 'active')))
    return new_id if ok else ""

def update_hospital(hospital_id, fields: dict) -> bool:
    allowed = ['address', 'contact_number', 'status', 'hospital_type']
    updates = []
    params = []
    for k, v in fields.items():
        if k in allowed:
            updates.append(f"{k} = ?")
            params.append(v)
    
    if not updates:
        return False
        
    params.append(hospital_id)
    return _x(f"UPDATE hospitals SET {', '.join(updates)} WHERE id = ?", tuple(params))

# ─────────────────────────────────────────────
# WORKERS / USERS
# ─────────────────────────────────────────────

def get_user_by_id(user_id):
    """Fetch a single user by their id. Returns dict or None."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_users():
    sql = """SELECT u.*, h.name as hospital_name 
             FROM users u 
             LEFT JOIN hospitals h ON u.hospital_id = h.id 
             WHERE u.role != 'super_admin' 
             ORDER BY h.name, u.full_name"""
    return _q(sql)

def get_workers_by_hospital(hospital_id=None):
    if hospital_id:
        sql = """SELECT u.*, h.name as hospital_name 
                 FROM users u 
                 LEFT JOIN hospitals h ON u.hospital_id = h.id 
                 WHERE u.hospital_id = ? AND u.role != 'super_admin' 
                 ORDER BY u.full_name"""
        return _q(sql, (hospital_id,))
    else:
        return get_all_users()

def deactivate_user(user_id) -> bool:
    return _x("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))

def reactivate_user(user_id) -> bool:
    return _x("UPDATE users SET is_active = 1 WHERE id = ?", (user_id,))

def reset_user_password(user_id, new_password) -> bool:
    hashed = _hash(new_password)
    return _x("UPDATE users SET password = ? WHERE id = ?", (hashed, user_id))

def update_user_role(user_id, new_role):
    if new_role not in ["hospital_admin", "staff"]:
        return False
    return _x("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))

def update_user_shift(user_id, shift, dept) -> bool:
    return _x("UPDATE users SET shift = ?, department = ? WHERE id = ?", (shift, dept, user_id))

# ─────────────────────────────────────────────
# BLOOD UNITS
# ─────────────────────────────────────────────

def get_blood_units(hospital_id=None) -> list:
    sql = """SELECT b.*, h.name as hospital_name,
             d.full_name as donor_name
             FROM blood_units b
             LEFT JOIN hospitals h ON b.hospital_id = h.id
             LEFT JOIN donors d ON b.donor_id = d.id
             WHERE b.status = 'available'"""
    params = ()
    if hospital_id:
        sql += " AND b.hospital_id=?"
        params = (hospital_id,)
    sql += " ORDER BY b.expiry_date ASC"
    units = _q(sql, params)
    today = datetime.now().date()
    for u in units:
        try:
            exp = datetime.fromisoformat(u["expiry_date"]).date()
            u["days_to_expiry"] = (exp - today).days
        except:
            u["days_to_expiry"] = 999
        u["unit_code"] = u["id"][:8].upper()
    return units

def get_expiring_units(days=3) -> list:
    target = str(datetime.now().date() + timedelta(days=days))
    units = _q("""SELECT b.*, h.name as hospital_name FROM blood_units b
                  LEFT JOIN hospitals h ON b.hospital_id=h.id
                  WHERE b.status='available' AND b.expiry_date <= ?
                  ORDER BY b.expiry_date ASC""", (target,))
    today = datetime.now().date()
    for u in units:
        try:
            exp = datetime.fromisoformat(u["expiry_date"]).date()
            u["days_to_expiry"] = (exp - today).days
        except:
            u["days_to_expiry"] = 999
        u["unit_code"] = u["id"][:8].upper()
    return units

def add_blood_unit(unit: dict) -> bool:
    uid = str(uuid.uuid4())
    return _x("""INSERT INTO blood_units (id,hospital_id,donor_id,blood_group,component,
                 volume_ml,collection_date,expiry_date,storage_temperature,status)
                 VALUES (?,?,?,?,?,?,?,?,?,?)""",
              (uid, unit.get("hospital_id"), unit.get("donor_id"),
               unit.get("blood_group"), unit.get("component"),
               unit.get("volume_ml", 450), unit.get("collection_date"),
               unit.get("expiry_date"), unit.get("storage_temperature", 4.0), "available"))

def update_unit_status(unit_id: str, status: str) -> bool:
    return _x("UPDATE blood_units SET status=? WHERE id=?", (status, unit_id))

def reserve_unit(unit_id: str) -> bool:
    return _x("UPDATE blood_units SET status='reserved' WHERE id=?", (unit_id,))

# ─────────────────────────────────────────────
# DONORS
# ─────────────────────────────────────────────

def get_donors(hospital_id=None) -> list:
    return _q("SELECT * FROM donors ORDER BY full_name")

def get_donor_by_id(did: str) -> dict:
    rows = _q("SELECT * FROM donors WHERE id=?", (did,))
    return rows[0] if rows else {}

def add_donor(donor: dict) -> bool:
    uid = str(uuid.uuid4())
    return _x("""INSERT INTO donors (id,cnic,full_name,blood_group,age,last_donation_date,
                 on_blood_thinners,risk_score,diseases,screening_hiv,screening_hepb,
                 screening_hepc,screening_syphilis,screening_malaria,created_at)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (uid, donor.get("cnic","00000-0000000-0"), donor.get("full_name"),
               donor.get("blood_group"), donor.get("age", 25),
               donor.get("last_donation_date",""), donor.get("on_blood_thinners", 0),
               donor.get("risk_score", 100), donor.get("diseases",""),
               donor.get("screening_hiv","passed"), donor.get("screening_hepb","passed"),
               donor.get("screening_hepc","passed"), donor.get("screening_syphilis","passed"),
               donor.get("screening_malaria","passed"), datetime.now().isoformat()))

# ─────────────────────────────────────────────
# PATIENTS
# ─────────────────────────────────────────────

def get_patients(hospital_id=None) -> list:
    if hospital_id:
        return _q("SELECT * FROM patients WHERE hospital_id=? ORDER BY full_name", (hospital_id,))
    return _q("SELECT * FROM patients ORDER BY full_name")

def get_patient_by_id(pid: str) -> dict:
    rows = _q("SELECT * FROM patients WHERE id=?", (pid,))
    return rows[0] if rows else {}

def add_patient(patient: dict) -> str:
    uid = str(uuid.uuid4())
    ok = _x("""INSERT INTO patients (id,hospital_id,cnic,full_name,father_name,age,gender,
               blood_group,mrn,ward,bed,opd_number,diagnosis,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uid, patient.get("hospital_id"), patient.get("cnic",""),
             patient.get("full_name"), patient.get("father_name",""),
             patient.get("age", 0), patient.get("gender",""),
             patient.get("blood_group"), patient.get("mrn",""),
             patient.get("ward",""), patient.get("bed",""),
             patient.get("opd_number",""), patient.get("diagnosis",""),
             datetime.now().isoformat()))
    return uid if ok else ""

# ─────────────────────────────────────────────
# CONTRACTS
# ─────────────────────────────────────────────

def get_active_contracts() -> list:
    rows = _q("""SELECT c.*,
                 lh.name as lending_hospital_name,
                 bh.name as borrowing_hospital_name
                 FROM contracts c
                 LEFT JOIN hospitals lh ON c.lending_hospital_id=lh.id
                 LEFT JOIN hospitals bh ON c.borrowing_hospital_id=bh.id
                 WHERE c.is_returned=0 AND c.status='active'
                 ORDER BY c.return_deadline ASC""")
    now = datetime.now()
    for r in rows:
        try:
            dl = datetime.fromisoformat(r["return_deadline"])
            r["hours_remaining"] = (dl - now).total_seconds() / 3600
            r["seconds_remaining"] = max(0, int((dl - now).total_seconds()))
        except:
            r["hours_remaining"] = 24
            r["seconds_remaining"] = 86400
    return rows

def create_contract(contract: dict) -> str:
    import random
    uid = str(uuid.uuid4())
    ticket = contract.get("ticket_id") or f"LF-{datetime.now().year}-{random.randint(1000,9999)}"
    issue_time = datetime.now().isoformat()
    deadline = (datetime.now() + timedelta(hours=contract.get("return_hours", 24))).isoformat()
    ok = _x("""INSERT INTO contracts (id,ticket_id,lending_hospital_id,borrowing_hospital_id,
               patient_id,blood_unit_id,blood_group,component,units,issue_time,
               return_deadline,status,is_exchange,is_returned)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uid, ticket, contract.get("lending_hospital_id"),
             contract.get("borrowing_hospital_id"), contract.get("patient_id"),
             contract.get("blood_unit_id"), contract.get("blood_group",""),
             contract.get("component",""), contract.get("units", 1),
             issue_time, deadline, "active",
             contract.get("is_exchange", 0), 0))
    return ticket if ok else ""

def update_contract_status(ticket_id: str, status: str) -> bool:
    return _x("UPDATE contracts SET status=? WHERE ticket_id=?", (status, ticket_id))

def mark_contract_returned(ticket_id: str) -> bool:
    return _x("UPDATE contracts SET is_returned=1, status='returned' WHERE ticket_id=?", (ticket_id,))

# ─────────────────────────────────────────────
# EXCHANGE OFFERS
# ─────────────────────────────────────────────

def get_exchange_offers(status=None) -> list:
    if status:
        rows = _q("""SELECT e.*, oh.name as offering_name, rh.name as receiving_name
                     FROM exchange_offers e
                     LEFT JOIN hospitals oh ON e.offering_hospital_id=oh.id
                     LEFT JOIN hospitals rh ON e.receiving_hospital_id=rh.id
                     WHERE e.status=?""", (status,))
    else:
        rows = _q("""SELECT e.*, oh.name as offering_name, rh.name as receiving_name
                     FROM exchange_offers e
                     LEFT JOIN hospitals oh ON e.offering_hospital_id=oh.id
                     LEFT JOIN hospitals rh ON e.receiving_hospital_id=rh.id""")
    for r in rows:
        r["offer_code"] = r["id"][:8].upper()
    return rows

def create_exchange_offer(offer: dict) -> str:
    uid = str(uuid.uuid4())
    ok = _x("""INSERT INTO exchange_offers (id,offering_hospital_id,receiving_hospital_id,
               offered_blood_group,requested_blood_group,units,status)
               VALUES (?,?,?,?,?,?,?)""",
            (uid, offer.get("offering_hospital_id"), offer.get("receiving_hospital_id"),
             offer.get("offered_blood_group"), offer.get("requested_blood_group"),
             offer.get("units", 1), offer.get("status","pending")))
    return uid if ok else ""

def update_exchange_offer(offer_id: str, status: str, matched_with=None) -> bool:
    if matched_with:
        return _x("UPDATE exchange_offers SET status=?, receiving_hospital_id=? WHERE id=?",
                  (status, matched_with, offer_id))
    return _x("UPDATE exchange_offers SET status=? WHERE id=?", (status, offer_id))

# ─────────────────────────────────────────────
# EMERGENCY REQUESTS
# ─────────────────────────────────────────────

def get_emergency_requests(hospital_id=None) -> list:
    if hospital_id:
        rows = _q("""SELECT e.*, rh.name as requesting_name
                     FROM emergency_requests e
                     LEFT JOIN hospitals rh ON e.requesting_hospital_id=rh.id
                     WHERE e.requesting_hospital_id=?
                     ORDER BY e.created_at DESC""", (hospital_id,))
    else:
        rows = _q("""SELECT e.*, rh.name as requesting_name
                     FROM emergency_requests e
                     LEFT JOIN hospitals rh ON e.requesting_hospital_id=rh.id
                     ORDER BY e.created_at DESC""")
    for r in rows:
        r["request_code"] = r["id"][:8].upper()
    return rows

def create_emergency_request(req: dict) -> str:
    uid = str(uuid.uuid4())
    ok = _x("""INSERT INTO emergency_requests (id,requesting_hospital_id,target_hospital_id,
               blood_group,component,units_required,urgency_level,status,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (uid, req.get("requesting_hospital_id"),
             req.get("target_hospital_id", req.get("requesting_hospital_id")),
             req.get("blood_group"), req.get("component","Whole Blood"),
             req.get("units_required", 1), req.get("urgency_level","Level 2 - Urgent"),
             req.get("status","pending"), datetime.now().isoformat()))
    return uid if ok else ""

def resolve_emergency(emg_id: str) -> bool:
    return _x("UPDATE emergency_requests SET status='resolved' WHERE id=?", (emg_id,))

# ─────────────────────────────────────────────
# AUDIT LOGS
# ─────────────────────────────────────────────

def add_audit_log(action, actor, hospital_id, entity_type, entity_id, details) -> bool:
    uid = str(uuid.uuid4())
    prev = _q("SELECT current_hash FROM audit_logs ORDER BY created_at DESC LIMIT 1")
    prev_hash = prev[0]["current_hash"] if prev else "genesis"
    payload = json.dumps(details) if isinstance(details, dict) else str(details)
    curr_hash = hashlib.sha256((prev_hash + payload).encode()).hexdigest()[:16]
    return _x("""INSERT INTO audit_logs (id,action,actor_id,hospital_id,entity_type,entity_id,
               details,previous_hash,current_hash,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
              (uid, action, str(actor), str(hospital_id) if hospital_id else "",
               entity_type, str(entity_id), payload, prev_hash, curr_hash,
               datetime.now().isoformat()))

def get_audit_logs(limit=50, hospital_id=None, actor_email=None) -> list:
    if actor_email:
        return _q("SELECT * FROM audit_logs WHERE actor_id=? ORDER BY created_at DESC LIMIT ?",
                  (actor_email, limit))
    if hospital_id:
        return _q("SELECT * FROM audit_logs WHERE hospital_id=? ORDER BY created_at DESC LIMIT ?",
                  (hospital_id, limit))
    return _q(f"SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT {limit}")

# ─────────────────────────────────────────────
# TRANSFUSION RECORDS
# ─────────────────────────────────────────────

def get_transfusion_records(hospital_id=None) -> list:
    if hospital_id:
        return _q("""SELECT t.*, p.full_name as patient_name, p.blood_group as patient_bg
                     FROM transfusion_records t
                     LEFT JOIN patients p ON t.patient_id=p.id
                     WHERE t.hospital_id=?
                     ORDER BY t.start_time DESC""", (hospital_id,))
    return _q("""SELECT t.*, p.full_name as patient_name, p.blood_group as patient_bg
                 FROM transfusion_records t
                 LEFT JOIN patients p ON t.patient_id=p.id
                 ORDER BY t.start_time DESC""")

def add_transfusion_record(record: dict) -> bool:
    uid = str(uuid.uuid4())
    return _x("""INSERT INTO transfusion_records (id,patient_id,unit_id,hospital_id,
               pre_bp_sys,pre_bp_dia,pre_pulse,pre_temp,pre_o2,
               post_bp_sys,post_bp_dia,post_pulse,post_temp,post_o2,
               reaction_type,action_taken,nurse_name,start_time,end_time)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (uid, record.get("patient_id"), record.get("unit_id"),
               record.get("hospital_id"), record.get("pre_bp_sys"),
               record.get("pre_bp_dia"), record.get("pre_pulse"),
               record.get("pre_temp"), record.get("pre_o2"),
               record.get("post_bp_sys"), record.get("post_bp_dia"),
               record.get("post_pulse"), record.get("post_temp"),
               record.get("post_o2"), record.get("reaction_type","none"),
               record.get("action_taken",""), record.get("nurse_name",""),
               record.get("start_time", datetime.now().isoformat()),
               record.get("end_time", datetime.now().isoformat())))

# ─────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────

def get_notifications(hospital_id=None, unread_only=False) -> list:
    base = "SELECT * FROM notifications"
    conds, params = [], []
    if hospital_id:
        conds.append("hospital_id=?"); params.append(hospital_id)
    if unread_only:
        conds.append("is_read=0")
    if conds:
        base += " WHERE " + " AND ".join(conds)
    base += " ORDER BY created_at DESC LIMIT 20"
    return _q(base, tuple(params))

def add_notification(hospital_id, ntype, title, message):
    uid = str(uuid.uuid4())
    _x("INSERT INTO notifications (id,hospital_id,type,title,message,created_at) VALUES (?,?,?,?,?,?)",
       (uid, hospital_id, ntype, title, message, datetime.now().isoformat()))

def mark_notifications_read(hospital_id):
    _x("UPDATE notifications SET is_read=1 WHERE hospital_id=?", (hospital_id,))

# ─────────────────────────────────────────────
# DASHBOARD STATS
# ─────────────────────────────────────────────

def get_dashboard_stats(hospital_id=None) -> dict:
    units = get_blood_units(hospital_id)
    expiring = get_expiring_units(3)
    if hospital_id:
        expiring = [u for u in expiring if u["hospital_id"] == hospital_id]

    groups = {}
    components = {}
    temp_alerts = 0
    for u in units:
        g = u.get("blood_group","?")
        groups[g] = groups.get(g, 0) + 1
        comp = u.get("component","?")
        components[comp] = components.get(comp, 0) + 1
        if u.get("storage_temperature", 4) > 6.0:
            temp_alerts += 1

    contracts = get_active_contracts()
    if hospital_id:
        contracts = [c for c in contracts if
                     c.get("lending_hospital_id") == hospital_id or
                     c.get("borrowing_hospital_id") == hospital_id]

    emgs = get_emergency_requests()
    active_emgs = [e for e in emgs if e.get("status") == "pending"]

    breach_risk = sum(1 for c in contracts if c.get("hours_remaining", 99) < 2)

    return {
        "total_units":         len(units),
        "expiring_3_days":     len(expiring),
        "active_contracts":    len(contracts),
        "live_emergencies":    len(active_emgs),
        "hospitals_online":    len(get_hospitals()),
        "screened_today":      len(get_donors()),
        "units_by_group":      groups,
        "units_by_component":  components,
        "temp_alerts":         temp_alerts,
        "breach_risk_contracts": breach_risk,
    }

def get_hospital_stats(hospital_id) -> dict:
    # worker_count, unit_count, active_contracts, departments{}
    workers = get_workers_by_hospital(hospital_id)
    units = get_blood_units(hospital_id)
    contracts = get_active_contracts()
    contracts = [c for c in contracts if c['lending_hospital_id'] == hospital_id or c['borrowing_hospital_id'] == hospital_id]
    
    depts = {}
    for w in workers:
        d = w.get('department', 'Unknown')
        depts[d] = depts.get(d, 0) + 1
        
    return {
        "worker_count": len(workers),
        "unit_count": len(units),
        "active_contracts": len(contracts),
        "departments": depts
    }

def seed_mock_data():
    return True
