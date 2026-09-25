"""Donors, screening tests, transfusions and users."""
from __future__ import annotations

import sqlite3
from typing import Any

from lifeline import clock


# ---------------------------------------------------------------- donors
def donor_insert(conn: sqlite3.Connection, *, name: str, cnic: str | None, phone: str | None, blood_group: str,
                 hospital_id: int, age: int | None, last_donated: str | None, eligible: bool, notes: str | None,
                 times_donated: int = 0) -> int:
    cur = conn.execute(
        "INSERT INTO donors (name, cnic, phone, blood_group, hospital_id, age, times_donated, last_donated, eligible, notes)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (name, cnic or None, phone, blood_group, hospital_id, age, times_donated, last_donated, int(eligible), notes))
    assert cur.lastrowid is not None
    return cur.lastrowid


def donor_get(conn: sqlite3.Connection, donor_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM donors WHERE id = ?", (donor_id,)).fetchone()
    return dict(row) if row else None


def donor_by_cnic(conn: sqlite3.Connection, cnic: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM donors WHERE cnic = ?", (cnic,)).fetchone()
    return dict(row) if row else None


def donor_set_eligible(conn: sqlite3.Connection, donor_id: int, eligible: bool) -> None:
    conn.execute("UPDATE donors SET eligible = ? WHERE id = ?", (int(eligible), donor_id))


def donors(conn: sqlite3.Connection, hospital_id: int | None) -> list[dict[str, Any]]:
    sql = ("SELECT d.*, h.name AS hospital_name FROM donors d LEFT JOIN hospitals h ON d.hospital_id = h.id"
           + (" WHERE d.hospital_id = ?" if hospital_id is not None else "") + " ORDER BY d.name")
    return [dict(r) for r in conn.execute(sql, (hospital_id,) if hospital_id is not None else ())]


# ---------------------------------------------------------------- screening
def screening_insert(conn: sqlite3.Connection, *, donor_id: int, hospital_id: int, hiv: bool, hepatitis_b: bool,
                     hepatitis_c: bool, syphilis: bool, malaria: bool, decision: str | None, risk_score: int | None,
                     created_by: int | None) -> int:
    result = "FAIL" if any((hiv, hepatitis_b, hepatitis_c, syphilis, malaria)) else "PASS"
    cur = conn.execute(
        "INSERT INTO screening_tests (donor_id, hospital_id, test_date, hiv, hepatitis_b, hepatitis_c, syphilis, malaria,"
        " result, decision, risk_score, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (donor_id, hospital_id, clock.now_iso(), int(hiv), int(hepatitis_b), int(hepatitis_c), int(syphilis), int(malaria),
         result, decision, risk_score, created_by))
    assert cur.lastrowid is not None
    return cur.lastrowid


def screenings(conn: sqlite3.Connection, hospital_id: int | None) -> list[dict[str, Any]]:
    sql = ("SELECT st.*, d.name AS donor_name, d.blood_group AS donor_blood_group FROM screening_tests st"
           " LEFT JOIN donors d ON st.donor_id = d.id"
           + (" WHERE st.hospital_id = ?" if hospital_id is not None else "") + " ORDER BY st.test_date DESC, st.id DESC")
    return [dict(r) for r in conn.execute(sql, (hospital_id,) if hospital_id is not None else ())]


# ---------------------------------------------------------------- transfusions
def transfusion_insert(conn: sqlite3.Connection, *, hospital_id: int, patient_name: str | None,
                       patient_blood_group: str, blood_group: str, units: int, performed_by: str | None,
                       notes: str | None, created_by: int | None) -> int:
    cur = conn.execute(
        "INSERT INTO transfusions (hospital_id, patient_name, patient_blood_group, blood_group, units, transfused_at,"
        " performed_by, notes, created_by) VALUES (?,?,?,?,?,?,?,?,?)",
        (hospital_id, patient_name, patient_blood_group, blood_group, units, clock.now_iso(), performed_by, notes, created_by))
    assert cur.lastrowid is not None
    return cur.lastrowid


def transfusions(conn: sqlite3.Connection, hospital_id: int | None) -> list[dict[str, Any]]:
    sql = ("SELECT t.*, h.name AS hospital_name FROM transfusions t JOIN hospitals h ON t.hospital_id = h.id"
           + (" WHERE t.hospital_id = ?" if hospital_id is not None else "") + " ORDER BY t.transfused_at DESC, t.id DESC")
    return [dict(r) for r in conn.execute(sql, (hospital_id,) if hospital_id is not None else ())]


# ---------------------------------------------------------------- users
def user_by_email(conn: sqlite3.Connection, email: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def user_by_id(conn: sqlite3.Connection, user_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def users(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(
        "SELECT u.*, h.name AS hospital_name FROM users u LEFT JOIN hospitals h ON u.hospital_id = h.id ORDER BY u.role, u.name")]


def user_insert(conn: sqlite3.Connection, email: str, password_hash: str, role: str, name: str,
                hospital_id: int | None) -> bool:
    """False if the email is taken; other integrity errors (bad role/hospital) propagate."""
    try:
        conn.execute("INSERT INTO users (email, password_hash, role, name, created_at, hospital_id) VALUES (?,?,?,?,?,?)",
                     (email.strip().lower(), password_hash, role, name, clock.now_iso(), hospital_id))
    except sqlite3.IntegrityError as exc:
        if "UNIQUE" in str(exc):
            return False
        raise
    return True


def person_names(conn: sqlite3.Connection) -> list[str]:
    """Every patient/donor/staff name, so free text can be scrubbed before it leaves the app."""
    rows = conn.execute(
        "SELECT patient_name AS n FROM blood_requests UNION SELECT patient_name FROM transfusions "
        "UNION SELECT performed_by FROM transfusions UNION SELECT name FROM donors UNION SELECT name FROM users").fetchall()
    return [r["n"] for r in rows if r["n"]]
