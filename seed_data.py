"""
seed_data.py — LIFELINE v5.0 Supabase Seed Script
Run once: python seed_data.py
Inserts: hospitals, users, donors, patients, blood_units, contracts, exchange_offers
Safe to re-run: skips rows that already exist (upsert on primary key).
"""
import os, uuid, hashlib, random
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()
from supabase import create_client
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def h(pw): return hashlib.sha256(pw.encode()).hexdigest()
def uid(): return str(uuid.uuid4())
def iso(d): return d.isoformat()
now = datetime.now()

print("🌱  LIFELINE Supabase Seed — starting...")

# ─────────────────────────────────────────────────────────────────
# 1. HOSPITALS
# ─────────────────────────────────────────────────────────────────
hospitals = [
    {"id":"h-mayo",     "name":"Mayo Hospital",                          "hospital_type":"Government","address":"Nila Gumbad, Lahore","contact_number":"042-99200600","lat":31.5651,"lng":74.3062,"status":"good"},
    {"id":"h-services", "name":"Services Hospital",                      "hospital_type":"Government","address":"Sir Ganga Ram Hospital Rd, Lahore","contact_number":"042-99203000","lat":31.5497,"lng":74.3436,"status":"good"},
    {"id":"h-jinnah",   "name":"Jinnah Hospital",                        "hospital_type":"Government","address":"Allama Iqbal Road, Lahore","contact_number":"042-99231301","lat":31.5204,"lng":74.3587,"status":"low"},
    {"id":"h-shaukat",  "name":"Shaukat Khanum Memorial Cancer Hospital","hospital_type":"Private",  "address":"7-A Block R-3 Johar Town, Lahore","contact_number":"042-35945100","lat":31.4697,"lng":74.2728,"status":"good"},
    {"id":"h-general",  "name":"Lahore General Hospital",                "hospital_type":"Government","address":"Jail Road, Lahore","contact_number":"042-99231601","lat":31.5560,"lng":74.3288,"status":"critical"},
]
res = sb.table("hospitals").upsert(hospitals, on_conflict="id").execute()
print(f"  ✅  hospitals: {len(res.data or [])} upserted")

# ─────────────────────────────────────────────────────────────────
# 2. USERS (SHA-256 password = 'lifeline123')
# ─────────────────────────────────────────────────────────────────
pw_hash = h("lifeline123")
users = [
    {"id":"u-admin",    "email":"admin@lifeline.com",    "password":"lifeline123","password_hash":pw_hash,"full_name":"Dr. Zara Ahmed",         "role":"super_admin",    "hospital_id":None,        "department":"Administration","shift":"Morning","is_active":1},
    {"id":"u-mayo",     "email":"mayo@lifeline.com",     "password":"lifeline123","password_hash":pw_hash,"full_name":"Dr. Kamran Sheikh",       "role":"hospital_admin", "hospital_id":"h-mayo",    "department":"Blood Bank",   "shift":"Morning","is_active":1},
    {"id":"u-services", "email":"services@lifeline.com", "password":"lifeline123","password_hash":pw_hash,"full_name":"Dr. Amna Malik",          "role":"hospital_admin", "hospital_id":"h-services","department":"Blood Bank",   "shift":"Morning","is_active":1},
    {"id":"u-staff",    "email":"staff@lifeline.com",    "password":"lifeline123","password_hash":pw_hash,"full_name":"Nurse Hira Baig",          "role":"staff",          "hospital_id":"h-mayo",    "department":"ICU",          "shift":"Evening","is_active":1},
    {"id":"u-jinnah",   "email":"jinnah@lifeline.com",   "password":"lifeline123","password_hash":pw_hash,"full_name":"Dr. Bilal Hassan",        "role":"hospital_admin", "hospital_id":"h-jinnah",  "department":"Blood Bank",   "shift":"Night",  "is_active":1},
]
res = sb.table("users").upsert(users, on_conflict="id").execute()
print(f"  ✅  users: {len(res.data or [])} upserted")

# ─────────────────────────────────────────────────────────────────
# 3. DONORS
# ─────────────────────────────────────────────────────────────────
blood_groups = ["A+","A-","B+","B-","O+","O-","AB+","AB-"]
donor_names = [
    ("Muhammad Ali","35202-1234567-1"),("Fatima Zahra","35202-2345678-2"),
    ("Ahmed Khan","35301-3456789-3"),  ("Ayesha Siddiq","35402-4567890-4"),
    ("Usman Tariq","35501-5678901-5"), ("Sara Noor","35601-6789012-6"),
    ("Imran Butt","35701-7890123-7"),  ("Zainab Malik","35801-8901234-8"),
    ("Asad Raza","35901-9012345-9"),   ("Maryam Shah","36001-0123456-0"),
    ("Tariq Mahmood","36101-1234560-1"),("Nadia Iqbal","36201-2345671-2"),
    ("Bilal Chaudhry","36301-3456782-3"),("Hina Qureshi","36401-4567893-4"),
    ("Faisal Abbasi","36501-5678904-5"),("Sana Riaz","36601-6789015-6"),
    ("Khalid Mehmood","36701-7890126-7"),("Rukhsana Bibi","36801-8901237-8"),
    ("Danial Waheed","36901-9012348-9"),("Saima Javed","37001-0123459-0"),
]
hosp_ids = ["h-mayo","h-services","h-jinnah","h-shaukat","h-general"]
donors = []
for i,(name,cnic) in enumerate(donor_names):
    bg = blood_groups[i % len(blood_groups)]
    risk = random.randint(55,100)
    donors.append({
        "id": f"d-{i+1:03d}",
        "full_name": name, "cnic": cnic, "age": random.randint(20,55),
        "blood_group": bg, "risk_score": risk, "hospital_id": hosp_ids[i % len(hosp_ids)],
        "diseases": "", "screening_hiv":"negative","screening_hepb":"negative",
        "screening_hepc":"negative","screening_syphilis":"negative","screening_malaria":"negative",
        "latitude": 31.5 + random.uniform(-0.1,0.1),
        "longitude": 74.35 + random.uniform(-0.1,0.1),
        "times_donated": random.randint(1,8),
        "last_donation_date": iso(date.today() - timedelta(days=random.randint(90,400))),
    })
res = sb.table("donors").upsert(donors, on_conflict="id").execute()
print(f"  ✅  donors: {len(res.data or [])} upserted")

# ─────────────────────────────────────────────────────────────────
# 4. BLOOD UNITS  (spread across 90 days, various expiry windows)
# ─────────────────────────────────────────────────────────────────
SHELF = {"Whole Blood":42,"RBC":42,"Platelets":5,"Plasma":365,"FFP":365}
components = list(SHELF.keys())
units = []
today = date.today()
for i in range(80):
    comp = random.choice(components)
    col_date = today - timedelta(days=random.randint(1,88))
    exp_date = col_date + timedelta(days=SHELF[comp])
    bg = blood_groups[i % len(blood_groups)]
    donor_id = donors[i % len(donors)]["id"]
    hosp = hosp_ids[i % len(hosp_ids)]
    # Some expired, most available
    status = "available"
    if exp_date < today:
        status = "expired"
    elif random.random() < 0.07:
        status = "reserved"
    units.append({
        "id": f"bu-{i+1:04d}",
        "hospital_id": hosp,
        "donor_id": donor_id,
        "blood_group": bg,
        "component": comp,
        "volume_ml": random.choice([350,400,450,500]),
        "collection_date": iso(col_date),
        "expiry_date": iso(exp_date),
        "storage_temperature": 4.0,
        "status": status,
    })
res = sb.table("blood_units").upsert(units, on_conflict="id").execute()
print(f"  ✅  blood_units: {len(res.data or [])} upserted")

# ─────────────────────────────────────────────────────────────────
# 5. PATIENTS
# ─────────────────────────────────────────────────────────────────
patient_names = [
    ("Rashid Ahmed","A+"),("Noor Bibi","B-"),("Sohail Akhtar","O+"),
    ("Fareeha Zaman","AB+"),("Junaid Qadir","A-"),("Mariam Tanvir","O-"),
    ("Wasim Akram","B+"),("Ghazala Parveen","AB-"),
]
patients = []
for i,(name,bg) in enumerate(patient_names):
    patients.append({
        "id": f"p-{i+1:03d}",
        "full_name": name, "blood_group": bg,
        "hospital_id": hosp_ids[i % len(hosp_ids)],
        "admission_date": iso(today - timedelta(days=random.randint(1,14))),
        "latitude": 31.5 + random.uniform(-0.08,0.08),
        "longitude": 74.35 + random.uniform(-0.08,0.08),
        "condition": random.choice(["Stable","Critical","Improving"]),
    })
try:
    res = sb.table("patients").upsert(patients, on_conflict="id").execute()
    print(f"  ✅  patients: {len(res.data or [])} upserted")
except Exception as e:
    print(f"  ⚠️  patients: {e} (table may not exist yet — skipping)")

# ─────────────────────────────────────────────────────────────────
# 6. CONTRACTS
# ─────────────────────────────────────────────────────────────────
contracts = [
    {
        "id":"c-001","ticket_id":"LF-2026-AA01",
        "lending_hospital_id":"h-mayo","borrowing_hospital_id":"h-jinnah",
        "blood_group":"O+","component":"RBC","units":4,
        "return_deadline": iso(now + timedelta(hours=36)),
        "status":"active","is_exchange":0,"created_at":iso(now - timedelta(hours=12)),
    },
    {
        "id":"c-002","ticket_id":"LF-2026-BB02",
        "lending_hospital_id":"h-services","borrowing_hospital_id":"h-general",
        "blood_group":"A+","component":"Platelets","units":2,
        "return_deadline": iso(now - timedelta(hours=2)),  # overdue
        "status":"active","is_exchange":0,"created_at":iso(now - timedelta(days=2)),
    },
    {
        "id":"c-003","ticket_id":"LF-2026-CC03",
        "lending_hospital_id":"h-jinnah","borrowing_hospital_id":"h-mayo",
        "blood_group":"B+","component":"Plasma","units":3,
        "return_deadline": iso(now + timedelta(days=5)),
        "status":"returned","is_exchange":0,"created_at":iso(now - timedelta(days=10)),
    },
    {
        "id":"c-004","ticket_id":"LF-2026-DD04",
        "lending_hospital_id":"h-shaukat","borrowing_hospital_id":"h-services",
        "blood_group":"AB-","component":"Whole Blood","units":1,
        "return_deadline": iso(now + timedelta(hours=8)),
        "status":"active","is_exchange":1,"created_at":iso(now - timedelta(hours=20)),
    },
    {
        "id":"c-005","ticket_id":"LF-2026-EE05",
        "lending_hospital_id":"h-general","borrowing_hospital_id":"h-shaukat",
        "blood_group":"O-","component":"RBC","units":5,
        "return_deadline": iso(now - timedelta(days=3)),
        "status":"breached","is_exchange":0,"created_at":iso(now - timedelta(days=8)),
    },
]
try:
    res = sb.table("contracts").upsert(contracts, on_conflict="id").execute()
    print(f"  ✅  contracts: {len(res.data or [])} upserted")
except Exception as e:
    print(f"  ⚠️  contracts: {e}")

# ─────────────────────────────────────────────────────────────────
# 7. EXCHANGE OFFERS
# ─────────────────────────────────────────────────────────────────
exchange_offers = [
    {"id":"ex-001","offering_hospital_id":"h-mayo",    "offered_blood_group":"A+","requested_blood_group":"O+","units":3,"status":"pending",  "created_at":iso(now - timedelta(hours=5))},
    {"id":"ex-002","offering_hospital_id":"h-services","offered_blood_group":"O+","requested_blood_group":"A+","units":3,"status":"matched",  "created_at":iso(now - timedelta(hours=4)),"receiving_hospital_id":"h-mayo"},
    {"id":"ex-003","offering_hospital_id":"h-jinnah",  "offered_blood_group":"B+","requested_blood_group":"AB+","units":2,"status":"pending", "created_at":iso(now - timedelta(hours=2))},
    {"id":"ex-004","offering_hospital_id":"h-shaukat", "offered_blood_group":"AB+","requested_blood_group":"B+","units":2,"status":"matched", "created_at":iso(now - timedelta(hours=1)),"receiving_hospital_id":"h-jinnah"},
]
try:
    res = sb.table("exchange_offers").upsert(exchange_offers, on_conflict="id").execute()
    print(f"  ✅  exchange_offers: {len(res.data or [])} upserted")
except Exception as e:
    print(f"  ⚠️  exchange_offers: {e}")

# ─────────────────────────────────────────────────────────────────
# 8. EMERGENCY REQUESTS
# ─────────────────────────────────────────────────────────────────
emergency_requests = [
    {"id":"er-001","requesting_hospital_id":"h-jinnah","target_hospital_id":"h-mayo",   "blood_group":"O-","component":"RBC",      "units_required":2,"urgency_level":"Critical","status":"pending",  "created_at":iso(now - timedelta(minutes=40))},
    {"id":"er-002","requesting_hospital_id":"h-general","target_hospital_id":"h-services","blood_group":"A+","component":"Platelets","units_required":4,"urgency_level":"Urgent",  "status":"resolved", "created_at":iso(now - timedelta(hours=3))},
    {"id":"er-003","requesting_hospital_id":"h-mayo",   "target_hospital_id":"h-shaukat","blood_group":"B-","component":"Plasma",   "units_required":1,"urgency_level":"Routine", "status":"pending",  "created_at":iso(now - timedelta(hours=1))},
]
try:
    res = sb.table("emergency_requests").upsert(emergency_requests, on_conflict="id").execute()
    print(f"  ✅  emergency_requests: {len(res.data or [])} upserted")
except Exception as e:
    print(f"  ⚠️  emergency_requests: {e}")

# ─────────────────────────────────────────────────────────────────
# 9. AUDIT LOGS
# ─────────────────────────────────────────────────────────────────
audit_logs = [
    {"id":"al-001","hospital_id":"h-mayo",    "actor_id":"u-mayo",    "action":"BLOOD_UNIT_REGISTERED","details":"Registered unit bu-0001 (A+)","entity_type":"blood_unit","entity_id":"bu-0001","created_at":iso(now - timedelta(hours=6))},
    {"id":"al-002","hospital_id":"h-services","actor_id":"u-services","action":"DONOR_SCREENED",        "details":"Screened donor Muhammad Ali",  "entity_type":"donor",     "entity_id":"d-001",  "created_at":iso(now - timedelta(hours=5))},
    {"id":"al-003","hospital_id":"h-jinnah",  "actor_id":"u-jinnah",  "action":"EMERGENCY_REQUEST",     "details":"Created request for 2x O-",   "entity_type":"request",   "entity_id":"er-001", "created_at":iso(now - timedelta(minutes=40))},
    {"id":"al-004","hospital_id":"h-mayo",    "actor_id":"u-mayo",    "action":"CONTRACT_CREATED",      "details":"Contract LF-2026-AA01 created","entity_type":"contract",  "entity_id":"c-001",  "created_at":iso(now - timedelta(hours=12))},
    {"id":"al-005","hospital_id":"h-services","actor_id":"u-admin",   "action":"EXCHANGE_MATCHED",      "details":"A+ <> O+ exchange matched",   "entity_type":"exchange",  "entity_id":"ex-002", "created_at":iso(now - timedelta(hours=4))},
]
try:
    res = sb.table("audit_logs").upsert(audit_logs, on_conflict="id").execute()
    print(f"  ✅  audit_logs: {len(res.data or [])} upserted")
except Exception as e:
    print(f"  ⚠️  audit_logs: {e}")

print("\n✅  Seed complete! All tables populated.")
print("    Login: admin@lifeline.com / lifeline123 (Super Admin)")
print("    Login: mayo@lifeline.com  / lifeline123 (Hospital Admin)")
print("    Login: staff@lifeline.com / lifeline123 (Staff)")
