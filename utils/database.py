# utils/database.py
from __future__ import annotations
import sqlite3
from datetime import datetime

from lifeline.db.connection import connect as _conn


def get_user_by_email(email: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def add_audit_log(action_type: str, description: str, user_id: int | None = None) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        conn.execute(
            "INSERT INTO audit_logs (action_type,description,user_id,timestamp) VALUES (?,?,?,?)",
            (action_type, description, user_id, now),
        )
        conn.commit()


def log_ai_usage(feature: str, input_summary: str, response_preview: str,
                 hospital_id: int | None = None, user_id: int | None = None) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        conn.execute(
            "INSERT INTO ai_logs (feature,input_summary,response_preview,hospital_id,user_id,created_at) VALUES (?,?,?,?,?,?)",
            (feature, input_summary, response_preview[:200], hospital_id, user_id, now),
        )
        conn.commit()


def get_all_hospitals() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM hospitals ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_hospital_by_id(hospital_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM hospitals WHERE id = ?", (hospital_id,)).fetchone()
    return dict(row) if row else None


def get_blood_units(hospital_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        if hospital_id:
            rows = conn.execute(
                "SELECT bu.*, h.name as hospital_name FROM blood_units bu "
                "JOIN hospitals h ON bu.hospital_id = h.id "
                "WHERE bu.hospital_id = ? ORDER BY expiry_date ASC",
                (hospital_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT bu.*, h.name as hospital_name FROM blood_units bu "
                "JOIN hospitals h ON bu.hospital_id = h.id ORDER BY expiry_date ASC"
            ).fetchall()
    return [dict(r) for r in rows]


def get_blood_summary(hospital_id: int | None = None) -> dict[str, int]:
    """Returns {blood_group: total_units} dict."""
    units = get_blood_units(hospital_id)
    summary: dict[str, int] = {}
    for u in units:
        bg = u["blood_group"]
        summary[bg] = summary.get(bg, 0) + u["units"]
    return summary


def update_blood_units(hospital_id: int, blood_group: str, delta: int,
                       reason: str = "", user_id: int | None = None) -> bool:
    """Add or subtract units from inventory. Returns True on success."""
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, units FROM blood_units WHERE hospital_id = ? AND blood_group = ? ORDER BY expiry_date ASC LIMIT 1",
            (hospital_id, blood_group)
        ).fetchone()
        if not row:
            return False
        new_units = max(0, row["units"] + delta)
        conn.execute(
            "UPDATE blood_units SET units = ?, updated_at = ? WHERE id = ?",
            (new_units, now, row["id"])
        )
        conn.execute(
            "INSERT INTO inventory_changes (hospital_id,blood_group,change_type,units_delta,reason,changed_at,changed_by) VALUES (?,?,?,?,?,?,?)",
            (hospital_id, blood_group, "ADD" if delta > 0 else "REMOVE", delta, reason, now, user_id)
        )
        conn.commit()
    return True


def add_blood_units(hospital_id: int, blood_group: str, units: int,
                    expiry_date: str, user_id: int | None = None) -> bool:
    """Insert a new blood unit record."""
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        conn.execute(
            "INSERT INTO blood_units (hospital_id,blood_group,units,expiry_date,updated_at) VALUES (?,?,?,?,?)",
            (hospital_id, blood_group, units, expiry_date, now)
        )
        conn.execute(
            "INSERT INTO inventory_changes (hospital_id,blood_group,change_type,units_delta,reason,changed_at,changed_by) VALUES (?,?,?,?,?,?,?)",
            (hospital_id, blood_group, "ADD", units, "New stock added", now, user_id)
        )
        conn.commit()
    return True


def get_donors(hospital_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        if hospital_id:
            rows = conn.execute(
                "SELECT d.*, h.name as hospital_name FROM donors d "
                "LEFT JOIN hospitals h ON d.hospital_id = h.id "
                "WHERE d.hospital_id = ? ORDER BY d.name",
                (hospital_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT d.*, h.name as hospital_name FROM donors d "
                "LEFT JOIN hospitals h ON d.hospital_id = h.id ORDER BY d.name"
            ).fetchall()
    return [dict(r) for r in rows]


def add_donor(name: str, cnic: str, phone: str, blood_group: str,
              hospital_id: int, last_donated: str | None = None,
              eligible: int = 1, notes: str = "") -> bool:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO donors (name,cnic,phone,blood_group,hospital_id,last_donated,eligible,notes) VALUES (?,?,?,?,?,?,?,?)",
            (name, cnic, phone, blood_group, hospital_id, last_donated, eligible, notes)
        )
        conn.commit()
    return True


def get_blood_requests(hospital_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        if hospital_id:
            rows = conn.execute(
                "SELECT br.*, h.name as hospital_name FROM blood_requests br "
                "JOIN hospitals h ON br.requesting_hospital_id = h.id "
                "WHERE br.requesting_hospital_id = ? ORDER BY br.created_at DESC",
                (hospital_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT br.*, h.name as hospital_name FROM blood_requests br "
                "JOIN hospitals h ON br.requesting_hospital_id = h.id ORDER BY br.created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def add_blood_request(hospital_id: int, blood_group: str, units_needed: int,
                      urgency: str = "ROUTINE", patient_name: str = "",
                      patient_condition: str = "") -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        conn.execute(
            "INSERT INTO blood_requests (requesting_hospital_id,blood_group,units_needed,urgency,status,patient_name,patient_condition,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (hospital_id, blood_group, units_needed, urgency, "PENDING", patient_name, patient_condition, now)
        )
        conn.commit()
    return True


def resolve_blood_request(request_id: int) -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        conn.execute(
            "UPDATE blood_requests SET status = 'RESOLVED', resolved_at = ? WHERE id = ?",
            (now, request_id)
        )
        conn.commit()
    return True


def get_transfusions(hospital_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        if hospital_id:
            rows = conn.execute(
                "SELECT t.*, h.name as hospital_name FROM transfusions t "
                "JOIN hospitals h ON t.hospital_id = h.id "
                "WHERE t.hospital_id = ? ORDER BY t.transfused_at DESC",
                (hospital_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT t.*, h.name as hospital_name FROM transfusions t "
                "JOIN hospitals h ON t.hospital_id = h.id ORDER BY t.transfused_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def add_transfusion(hospital_id: int, patient_name: str, blood_group: str,
                    units: int, performed_by: str = "", notes: str = "") -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        conn.execute(
            "INSERT INTO transfusions (hospital_id,patient_name,blood_group,units,transfused_at,performed_by,notes) VALUES (?,?,?,?,?,?,?)",
            (hospital_id, patient_name, blood_group, units, now, performed_by, notes)
        )
        conn.commit()
    return True


def get_exchanges(hospital_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        if hospital_id:
            rows = conn.execute(
                "SELECT e.*, hf.name as from_name, ht.name as to_name "
                "FROM exchanges e "
                "JOIN hospitals hf ON e.from_hospital_id = hf.id "
                "JOIN hospitals ht ON e.to_hospital_id = ht.id "
                "WHERE e.from_hospital_id = ? OR e.to_hospital_id = ? "
                "ORDER BY e.created_at DESC",
                (hospital_id, hospital_id)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT e.*, hf.name as from_name, ht.name as to_name "
                "FROM exchanges e "
                "JOIN hospitals hf ON e.from_hospital_id = hf.id "
                "JOIN hospitals ht ON e.to_hospital_id = ht.id "
                "ORDER BY e.created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def add_exchange(from_hospital_id: int, to_hospital_id: int, blood_group: str, units: int) -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        conn.execute(
            "INSERT INTO exchanges (from_hospital_id,to_hospital_id,blood_group,units,status,created_at) VALUES (?,?,?,?,?,?)",
            (from_hospital_id, to_hospital_id, blood_group, units, "PENDING", now)
        )
        conn.commit()
    return True


def get_contracts(hospital_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        if hospital_id:
            rows = conn.execute(
                "SELECT c.*, h.name as hospital_name FROM contracts c "
                "JOIN hospitals h ON c.hospital_id = h.id "
                "WHERE c.hospital_id = ? ORDER BY c.contract_end ASC",
                (hospital_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT c.*, h.name as hospital_name FROM contracts c "
                "JOIN hospitals h ON c.hospital_id = h.id ORDER BY c.contract_end ASC"
            ).fetchall()
    return [dict(r) for r in rows]


def add_contract(hospital_id: int, vendor_name: str, blood_group: str,
                 units_per_month: int, contract_start: str, contract_end: str) -> bool:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO contracts (hospital_id,vendor_name,blood_group,units_per_month,contract_start,contract_end,status) VALUES (?,?,?,?,?,?,?)",
            (hospital_id, vendor_name, blood_group, units_per_month, contract_start, contract_end, "ACTIVE")
        )
        conn.commit()
    return True


def get_screening_tests(hospital_id: int | None = None) -> list[dict]:
    with _conn() as conn:
        if hospital_id:
            rows = conn.execute(
                "SELECT st.*, d.name as donor_name, d.blood_group as donor_blood_group "
                "FROM screening_tests st "
                "LEFT JOIN donors d ON st.donor_id = d.id "
                "WHERE st.hospital_id = ? ORDER BY st.test_date DESC",
                (hospital_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT st.*, d.name as donor_name, d.blood_group as donor_blood_group "
                "FROM screening_tests st "
                "LEFT JOIN donors d ON st.donor_id = d.id "
                "ORDER BY st.test_date DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def add_screening_test(donor_id: int | None, hospital_id: int,
                       hiv: bool = False, hepatitis_b: bool = False,
                       hepatitis_c: bool = False, syphilis: bool = False,
                       malaria: bool = False) -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    result = "PASS" if not any([hiv, hepatitis_b, hepatitis_c, syphilis, malaria]) else "FAIL"
    with _conn() as conn:
        conn.execute(
            "INSERT INTO screening_tests (donor_id,hospital_id,test_date,hiv,hepatitis_b,hepatitis_c,syphilis,malaria,result) VALUES (?,?,?,?,?,?,?,?,?)",
            (donor_id, hospital_id, now, int(hiv), int(hepatitis_b), int(hepatitis_c), int(syphilis), int(malaria), result)
        )
        conn.commit()
    return True


def get_audit_logs(limit: int = 100) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT al.*, u.name as user_name FROM audit_logs al "
            "LEFT JOIN users u ON al.user_id = u.id "
            "ORDER BY al.timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_inventory_changes(hospital_id: int | None = None, limit: int = 50) -> list[dict]:
    with _conn() as conn:
        if hospital_id:
            rows = conn.execute(
                "SELECT * FROM inventory_changes WHERE hospital_id = ? ORDER BY changed_at DESC LIMIT ?",
                (hospital_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM inventory_changes ORDER BY changed_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def get_all_users() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT u.*, h.name as hospital_name FROM users u "
            "LEFT JOIN hospitals h ON u.hospital_id = h.id ORDER BY u.role, u.name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_ai_logs(limit: int = 50) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM ai_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def add_user(email: str, password_hash: str, role: str, name: str,
             hospital_id: int | None = None) -> bool:
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as conn:
        try:
            conn.execute(
                "INSERT INTO users (email,password_hash,role,name,created_at,hospital_id) VALUES (?,?,?,?,?,?)",
                (email.strip().lower(), password_hash, role, name, now, hospital_id)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError as exc:
            if "UNIQUE" in str(exc):
                return False        # duplicate email; anything else (bad role/hospital) is a real error
            raise


def update_password_hash(user_id: int, password_hash: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


def get_dashboard_stats(hospital_id: int | None = None) -> dict:
    """Aggregate KPIs for dashboard display."""
    units = get_blood_units(hospital_id)
    total_units = sum(u["units"] for u in units)
    donors = get_donors(hospital_id)
    requests = get_blood_requests(hospital_id)
    pending_requests = len([r for r in requests if r.get("status") == "PENDING"])

    bg_summary: dict[str, int] = {}
    for u in units:
        bg = u["blood_group"]
        bg_summary[bg] = bg_summary.get(bg, 0) + u["units"]

    critical_groups = [bg for bg, count in bg_summary.items() if count < 5]

    return {
        "total_units": total_units,
        "total_donors": len(donors),
        "pending_requests": pending_requests,
        "critical_groups": critical_groups,
        "blood_summary": bg_summary,
    }
