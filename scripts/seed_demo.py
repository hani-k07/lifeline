"""Deterministic demo data (random.Random(42)): 10 Lahore hospitals, 11 demo users, 72 donors, 30 days of stock and
usage history (~2,000 units), and a mix of emergencies, exchanges and loans created through the real services.

Blood-group mix follows published Pakistani ABO/Rh surveys (B+ and O+ dominant, AB- rarest). The figures are
approximate; replace WEIGHTS with your own blood bank's statistics. Hospital coordinates are approximate (+-500 m)
public-map positions - verify them before any operational use."""
from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from lifeline import clock
from lifeline.auth.passwords import hash_password
from lifeline.db.connection import connect
from lifeline.demo import DEMO_PASSWORD, DEMO_USERS
from lifeline.engine.compatibility import can_donate, compatible_recipient_groups, rank_donor_groups
from lifeline.errors import DomainError
from lifeline.services import contracts, emergency, exchanges, housekeeping

WEIGHTS = {"B+": 0.32, "O+": 0.27, "A+": 0.21, "AB+": 0.08, "B-": 0.04, "O-": 0.035, "A-": 0.03, "AB-": 0.005}
SHELF_LIFE_DAYS = 35
HISTORY_DAYS = 30

# id, name, address, latitude, longitude, phone. Ids 1-4 are referenced by the demo users.
HOSPITALS = [
    (1, "Mayo Hospital", "Nila Gumbad, Anarkali, Lahore", 31.5716, 74.3159, "042-99211100"),
    (2, "Services Hospital", "Jail Road, Lahore", 31.5360, 74.3360, "042-99203402"),
    (3, "Jinnah Hospital", "Allama Iqbal Road, Lahore", 31.4815, 74.3030, "042-99231400"),
    (4, "Shaukat Khanum Memorial Hospital", "Johar Town, Lahore", 31.4670, 74.2700, "042-35905000"),
    (5, "Lahore General Hospital", "Ferozepur Road, Lahore", 31.5230, 74.3310, "042-99268801"),
    (6, "CMH Lahore", "Lahore Cantonment", 31.5470, 74.3650, "042-99220100"),
    (7, "Sheikh Zayed Hospital", "Zahoor Elahi Road, Lahore", 31.4930, 74.3230, "042-35865731"),
    (8, "Ittefaq Hospital", "Model Town, Lahore", 31.4830, 74.3220, "042-35861999"),
    (9, "Children's Hospital Lahore", "Ferozepur Road, Lahore", 31.4890, 74.3290, "042-99230801"),
    (10, "Punjab Institute of Cardiology", "Jail Road, Lahore", 31.5330, 74.3390, "042-99203051"),
]

FIRST = ["Ahmed", "Ali", "Bilal", "Hassan", "Usman", "Imran", "Kamran", "Asad", "Faisal", "Hamza", "Saad", "Umar",
         "Fatima", "Ayesha", "Sara", "Zainab", "Maryam", "Hina", "Nadia", "Rabia", "Sana", "Iqra", "Amna", "Noor"]
LAST = ["Khan", "Malik", "Butt", "Sheikh", "Chaudhry", "Raza", "Hussain", "Iqbal", "Ahmed", "Qureshi", "Shah", "Baig",
        "Mirza", "Siddiqui", "Farooq", "Ansari", "Javed", "Riaz"]
CONDITIONS = ["Trauma surgery", "Road accident", "Postpartum haemorrhage", "Thalassaemia transfusion", "GI bleed",
              "Cardiac surgery", "Chemotherapy support", "Severe anaemia"]


@dataclass(frozen=True)
class _Admin:
    id: int | None
    hospital_id: int | None = None
    is_super: bool = True


def _at(day: date, rng: random.Random, start: int = 8, end: int = 20) -> str:
    stamp = datetime.combine(day, time(rng.randint(start, end), rng.randint(0, 59), rng.randint(0, 59)), tzinfo=clock.PKT)
    return stamp.isoformat(timespec="seconds")


def seed_reference(conn: sqlite3.Connection) -> None:
    """Hospitals only: the reference data every installation needs."""
    conn.executemany(
        "INSERT OR IGNORE INTO hospitals (id, name, city, address, latitude, longitude, phone) VALUES (?,?,'Lahore',?,?,?,?)",
        HOSPITALS)
    conn.commit()


def seed_users(conn: sqlite3.Connection) -> None:
    now = clock.now_iso()
    conn.executemany(
        "INSERT OR IGNORE INTO users (email, password_hash, role, name, created_at, hospital_id) VALUES (?,?,?,?,?,?)",
        [(u.email, hash_password(DEMO_PASSWORD), u.role.value, u.name, now, u.hospital_id) for u in DEMO_USERS])


def _seed_donors(conn: sqlite3.Connection, rng: random.Random, today: date, count: int = 72) -> None:
    groups, weights = list(WEIGHTS), list(WEIGHTS.values())
    used: set[str] = set()
    rows = []
    for _ in range(count):
        while True:
            cnic = f"3520{rng.randint(1, 9)}-{rng.randint(1000000, 9999999)}-{rng.randint(1, 9)}"
            if cnic not in used:
                used.add(cnic)
                break
        times = rng.randint(0, 12)
        last = (today - timedelta(days=rng.randint(20, 400))).isoformat() if times else None
        phone = f"03{rng.randint(0, 4)}{rng.randint(0, 9)}-{rng.randint(1000000, 9999999)}"
        rows.append((f"{rng.choice(FIRST)} {rng.choice(LAST)}", cnic, phone,
                     rng.choices(groups, weights)[0], rng.randint(1, len(HOSPITALS)), rng.randint(18, 60), times, last,
                     0 if rng.random() < 0.08 else 1))
    conn.executemany(
        "INSERT INTO donors (name, cnic, phone, blood_group, hospital_id, age, times_donated, last_donated, eligible)"
        " VALUES (?,?,?,?,?,?,?,?,?)", rows)


def _simulate_history(conn: sqlite3.Connection, rng: random.Random, today: date) -> None:
    """Day-by-day stock in/out for every hospital over the last HISTORY_DAYS days, written as units + events."""
    groups, weights = list(WEIGHTS), list(WEIGHTS.values())
    start = today - timedelta(days=HISTORY_DAYS)
    units: list[dict] = []
    events: list[tuple] = []          # (at, unit index, hospital_id, group, type, note)
    live: dict[int, list[dict]] = {h[0]: [] for h in HOSPITALS}

    def new_unit(hospital: int, collected: date, at: str, group: str | None = None) -> dict:
        unit = {"hospital": hospital, "group": group or rng.choices(groups, weights)[0], "collected": collected,
                "expiry": collected + timedelta(days=SHELF_LIFE_DAYS), "status": "available", "changed": at, "created": at,
                "idx": len(units)}
        units.append(unit)
        live[hospital].append(unit)
        events.append((at, unit["idx"], hospital, unit["group"], "received", None))
        return unit

    for hospital in live:                                             # opening stock
        for _ in range(45):
            collected = start - timedelta(days=rng.randint(1, 25))
            new_unit(hospital, collected, _at(collected, rng), "O-" if _ < 2 else None)   # blood banks hold back O-
    for offset in range(HISTORY_DAYS):
        day = start + timedelta(days=offset)
        for hospital, stock in live.items():
            for unit in [u for u in stock if u["expiry"] < day]:      # expiry sweep
                unit["status"], unit["changed"] = "expired", _at(day, rng, 0, 1)
                events.append((unit["changed"], unit["idx"], hospital, unit["group"], "expired", "past expiry date"))
                stock.remove(unit)
            if (offset + hospital) % 2 == 0:                          # a delivery every other day
                for k in range(rng.randint(6, 10)):
                    new_unit(hospital, day, _at(day, rng, 7, 11), "O-" if k == 0 and offset % 6 == 0 else None)
            for _ in range(rng.randint(2, 6)):                        # patients use blood every day
                group = rng.choices(groups, weights)[0]
                candidates = sorted((u for u in stock if u["group"] == group), key=lambda u: (u["expiry"], u["idx"]))
                if not candidates:
                    continue
                unit = candidates[0]
                kind = "discarded" if rng.random() < 0.01 else ("transfused" if rng.random() < 0.7 else "issued")
                unit["status"], unit["changed"] = kind, _at(day, rng)
                events.append((unit["changed"], unit["idx"], hospital, group, kind, None))
                stock.remove(unit)

    conn.executemany(
        "INSERT INTO blood_units (id, unit_code, hospital_id, blood_group, collected_at, expiry_date, status, status_changed_at,"
        " created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        [(u["idx"] + 1, f"U{u['idx'] + 1:07d}", u["hospital"], u["group"], u["collected"].isoformat(), u["expiry"].isoformat(),
          u["status"], u["changed"], u["created"]) for u in units])
    conn.executemany(
        "INSERT INTO inventory_events (at, unit_id, hospital_id, blood_group, event_type, note) VALUES (?,?,?,?,?,?)",
        [(at, idx + 1, h, g, t, n) for at, idx, h, g, t, n in sorted(events)])

    # every transfused unit belongs to a transfusion record (same hospital, day and group share one)
    patients = [f"{rng.choice(FIRST)} {rng.choice(LAST)}" for _ in range(40)]
    batches: dict[tuple, list[dict]] = {}
    for u in units:
        if u["status"] == "transfused":
            batches.setdefault((u["hospital"], u["changed"][:10], u["group"]), []).append(u)
    for (hospital, _day, group), members in sorted(batches.items()):
        for i in range(0, len(members), 2):
            chunk = members[i:i + 2]
            patient_group = rng.choices([g for g in compatible_recipient_groups(group)],
                                        [3 if g == group else 1 for g in compatible_recipient_groups(group)])[0]
            cur = conn.execute(
                "INSERT INTO transfusions (hospital_id, patient_name, patient_blood_group, blood_group, units, transfused_at,"
                " performed_by) VALUES (?,?,?,?,?,?,?)",
                (hospital, rng.choice(patients), patient_group, group, len(chunk), chunk[-1]["changed"], "Ward staff"))
            conn.executemany("UPDATE blood_units SET transfusion_id = ? WHERE id = ?",
                             [(cur.lastrowid, u["idx"] + 1) for u in chunk])


def _reserve_anywhere(actor: _Admin, request_id: int, group: str, count: int, rng: random.Random) -> bool:
    sources = [h[0] for h in HOSPITALS]
    rng.shuffle(sources)
    for unit_group in rank_donor_groups(group):
        for source in sources:
            try:
                emergency.reserve_units(actor, request_id, source, unit_group, count)
                return True
            except DomainError:
                continue
    return False


def _seed_operations(rng: random.Random, admin_id: int) -> None:
    """Emergencies, exchanges and loans, created through the services exactly as the app does."""
    actor = _Admin(admin_id)
    patients = [f"{rng.choice(FIRST)} {rng.choice(LAST)}" for _ in range(8)]
    plan = [("PENDING", "CRITICAL"), ("PENDING", "URGENT"), ("PENDING", "ROUTINE"), ("RESERVED", "CRITICAL"),
            ("RESERVED", "URGENT"), ("RESOLVED", "URGENT"), ("RESOLVED", "ROUTINE"), ("CANCELLED", "ROUTINE")]
    for (target, urgency), patient in zip(plan, patients, strict=True):
        group = rng.choices(list(WEIGHTS), list(WEIGHTS.values()))[0]
        units = rng.randint(1, 3)
        hospital = rng.randint(1, len(HOSPITALS))
        request_id = emergency.create_request(actor, hospital, group, units, urgency, patient, rng.choice(CONDITIONS))
        if target == "PENDING":
            continue
        if not _reserve_anywhere(actor, request_id, group, units, rng):
            continue
        if target == "RESOLVED":
            emergency.fulfil_request(actor, request_id)
        elif target == "CANCELLED":
            emergency.cancel_request(actor, request_id, "patient transferred")

    def pair() -> tuple[int, int]:
        supplier, requester = rng.sample(range(1, len(HOSPITALS) + 1), 2)
        return supplier, requester

    for step in ("pending", "pending", "accepted", "completed", "rejected"):
        supplier, requester = pair()
        group = rng.choice(["B+", "O+", "A+"])
        try:
            exchange_id = exchanges.request_exchange(actor, supplier, requester, group, rng.randint(2, 4))
            if step in ("accepted", "completed"):
                exchanges.respond_exchange(actor, exchange_id, True)
            if step == "completed":
                exchanges.complete_exchange(actor, exchange_id)
            if step == "rejected":
                exchanges.respond_exchange(actor, exchange_id, False)
        except DomainError:
            continue

    now = clock.now()
    for step in ("active", "active", "returned", "returned", "late"):
        lender, borrower = pair()
        group = rng.choice(["B+", "O+", "A+"])
        try:
            deadline = now + (timedelta(hours=1) if step == "late" else timedelta(days=rng.randint(2, 7)))
            contract_id = contracts.create_loan(actor, lender, borrower, group, rng.randint(2, 5), deadline)
            if step == "returned":
                contracts.return_loan(actor, contract_id)
            if step == "late":                                       # the deadline slips into the past; housekeeping flags it
                with connect() as conn:
                    conn.execute("UPDATE contracts SET return_deadline = ? WHERE id = ?",
                                 ((now - timedelta(days=1)).isoformat(timespec="seconds"), contract_id))
        except DomainError:
            continue


def seed_demo(conn: sqlite3.Connection, *, seed: int = 42, today: date | None = None) -> None:
    """Populate an empty, freshly created database. `conn` must be idle (committed) when the services run."""
    rng = random.Random(seed)
    today = today or clock.today()
    seed_reference(conn)
    seed_users(conn)
    _seed_donors(conn, rng, today)
    _simulate_history(conn, rng, today)
    conn.commit()
    admin_id = int(conn.execute("SELECT id FROM users WHERE email = 'admin@lifeline.com'").fetchone()[0])
    _seed_operations(rng, admin_id)
    housekeeping.run()


__all__ = ["HOSPITALS", "WEIGHTS", "can_donate", "seed_demo", "seed_reference", "seed_users"]
