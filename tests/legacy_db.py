"""Builders for databases as they looked at older schema versions, with deliberately messy data."""
from __future__ import annotations

import sqlite3
from pathlib import Path

V1_SCHEMA = (Path(__file__).parent / "fixtures" / "v1_schema.sql").read_text(encoding="utf-8")

_V0_ROLE_CHECK = "CHECK(role IN ('admin','hospital','staff'))"
_V1_ROLE_CHECK = "CHECK(role IN ('super_admin','hospital_admin','staff'))"


def make_v1(path: Path, *, messy: bool = True) -> Path:
    """user_version 1: aggregated blood_units, vendor contracts, inventory_changes deltas."""
    conn = sqlite3.connect(path)
    conn.executescript(V1_SCHEMA)
    conn.execute("PRAGMA user_version = 1")
    conn.executescript(
        """
        INSERT INTO hospitals (id, name, city, latitude, longitude) VALUES
            (1, 'Mayo', 'Lahore', 31.57, 74.31), (2, 'Services', 'Lahore', 31.54, 74.34);
        INSERT INTO users (email, password_hash, role, name, created_at, hospital_id) VALUES
            ('a@x.pk', 'h', 'super_admin', 'A', '2026-06-01T00:00:00', NULL),
            ('n@x.pk', 'h', 'staff', 'N', '2026-06-01T00:00:00', 1);
        INSERT INTO audit_logs (action_type, description, user_id, timestamp)
            VALUES ('LOGIN', 'a logged in', 1, '2026-06-01T09:00:00');
        INSERT INTO blood_units (hospital_id, blood_group, units, expiry_date, updated_at) VALUES
            (1, 'A+', 3, '2999-01-01', '2026-06-11T00:42:22'),
            (1, 'O-', 2, '2000-01-01', '2026-06-11T00:42:22'),
            (2, 'B+', 0, '2999-01-01', '2026-06-11T00:42:22');
        INSERT INTO donors (name, cnic, phone, blood_group, hospital_id, last_donated, eligible)
            VALUES ('Ali', '35202-1111111-1', '0300', 'O+', 1, '2026-01-01', 1);
        INSERT INTO blood_requests (requesting_hospital_id, blood_group, units_needed, urgency, status, patient_name,
                                    created_at) VALUES (1, 'A+', 2, 'CRITICAL', 'PENDING', 'P', '2026-06-01T10:00:00');
        INSERT INTO transfusions (hospital_id, patient_name, blood_group, units, transfused_at)
            VALUES (1, 'P', 'A+', 1, '2026-06-02T10:00:00');
        INSERT INTO exchanges (from_hospital_id, to_hospital_id, blood_group, units, status, created_at)
            VALUES (2, 1, 'B+', 2, 'PENDING', '2026-06-03T10:00:00');
        INSERT INTO contracts (hospital_id, vendor_name, blood_group, units_per_month, contract_start, contract_end)
            VALUES (1, 'Punjab Blood Service', 'A+', 50, '2026-06-01', '2027-06-01');
        INSERT INTO inventory_changes (hospital_id, blood_group, change_type, units_delta, reason, changed_at, changed_by)
            VALUES (1, 'A+', 'ADD', 3, 'stock', '2026-06-11T00:42:22', 1),
                   (1, 'A+', 'REMOVE', -2, 'surgery', '2026-06-12T09:00:00', 2);
        INSERT INTO screening_tests (donor_id, hospital_id, test_date, hiv, result)
            VALUES (1, 1, '2026-06-05', 0, 'PASS');
        """
    )
    if messy:
        conn.executescript(
            """
            INSERT INTO blood_units (hospital_id, blood_group, units, expiry_date, updated_at) VALUES
                (1, 'ZZ', 4, '2999-01-01', '2026-06-11T00:42:22'),      -- invalid group
                (1, 'A-', 2, NULL,         '2026-06-11T00:42:22'),      -- no expiry: unsafe, must not become stock
                (1, 'B-', -5, '2999-01-01', '2026-06-11T00:42:22');     -- negative units
            INSERT INTO donors (name, cnic, blood_group, hospital_id)
                VALUES ('Duplicate Ali', '35202-1111111-1', 'O+', 1),   -- duplicate CNIC
                       ('Bad Group', NULL, 'Q', 1);
            INSERT INTO blood_requests (requesting_hospital_id, blood_group, units_needed, created_at)
                VALUES (1, 'A+', 0, '2026-06-01T10:00:00');             -- zero units
            INSERT INTO exchanges (from_hospital_id, to_hospital_id, blood_group, units, created_at)
                VALUES (1, 1, 'A+', 1, '2026-06-03T10:00:00');          -- to itself
            INSERT INTO inventory_changes (hospital_id, blood_group, change_type, units_delta, changed_at)
                VALUES (1, 'A+', 'ADD', 0, '2026-06-13T00:00:00');      -- zero delta
            """
        )
    conn.commit()
    conn.close()
    return path


def make_v0(path: Path) -> Path:
    """user_version 0: the original role vocabulary and no login_throttle table."""
    conn = sqlite3.connect(path)
    conn.executescript(V1_SCHEMA.replace(_V1_ROLE_CHECK, _V0_ROLE_CHECK))
    conn.execute("DROP TABLE login_throttle")
    conn.executescript(
        """
        INSERT INTO hospitals (id, name, city) VALUES (1, 'Mayo', 'Lahore');
        INSERT INTO users (email, password_hash, role, name, created_at, hospital_id) VALUES
            ('a@x.pk', 'h', 'admin', 'A', 't', NULL), ('h@x.pk', 'h', 'hospital', 'H', 't', 1),
            ('s@x.pk', 'h', 'staff', 'S', 't', 1);
        INSERT INTO audit_logs (action_type, description, user_id, timestamp) VALUES ('LOGIN', 'x', 2, 't');
        """
    )
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    conn.close()
    return path
