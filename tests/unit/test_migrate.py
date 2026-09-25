import sqlite3

import pytest

from lifeline.config import get_settings
from lifeline.db import migrate
from lifeline.db.schema import create_schema
from tests.legacy_db import make_v0, make_v1


def rows(conn, sql, *args):
    return [tuple(r) for r in conn.execute(sql, args)]


# ---------------------------------------------------------------- v0 -> latest (001 then 002)

def test_v0_roles_are_migrated_and_data_kept():
    path = make_v0(get_settings().db_path)
    assert migrate.ensure_schema() == [1, 2]
    conn = sqlite3.connect(path)
    assert dict(rows(conn, "SELECT email, role FROM users")) == {
        "a@x.pk": "super_admin", "h@x.pk": "hospital_admin", "s@x.pk": "staff"}
    assert rows(conn, "SELECT user_id FROM audit_logs") == [(2,)]          # FK target survived both rebuilds
    assert conn.execute("PRAGMA user_version").fetchone()[0] == migrate.LATEST_VERSION
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO users (email,password_hash,role,name,created_at) VALUES ('x','h','admin','X','t')")


def test_first_migration_leaves_a_backup_of_the_original():
    path = make_v0(get_settings().db_path)
    migrate.ensure_schema()
    backup = path.with_name(path.name + ".bak-v0")
    assert backup.exists()
    assert {r[0] for r in sqlite3.connect(backup).execute("SELECT role FROM users")} == {"admin", "hospital", "staff"}
    migrate.ensure_schema()                                                # no second backup, no overwrite
    assert sorted(p.name for p in path.parent.glob("*.bak-*")) == [backup.name]


def test_migration_is_idempotent_and_missing_db_is_reported():
    make_v0(get_settings().db_path)
    assert migrate.ensure_schema() == [1, 2]
    assert migrate.ensure_schema() == []


def test_missing_database_is_reported(tmp_path):
    with pytest.raises(migrate.DatabaseNotInitialised):
        migrate.ensure_schema()


# ---------------------------------------------------------------- v1 -> v2 (the unit ledger)

@pytest.fixture
def migrated(tmp_path):
    conn = sqlite3.connect(make_v1(tmp_path / "v1.db"))
    assert migrate.apply_migrations(conn) == [2]
    yield conn
    conn.close()


def test_aggregated_stock_becomes_individual_units(migrated):
    assert rows(migrated, "SELECT blood_group, status, COUNT(*) FROM blood_units GROUP BY 1, 2 ORDER BY 1") == [
        ("A+", "available", 3), ("O-", "expired", 2)]          # 3 + 2 units; the 2000-01-01 batch is already expired
    codes = [r[0] for r in migrated.execute("SELECT unit_code FROM blood_units ORDER BY id")]
    assert len(set(codes)) == 5 and all(c.startswith("U") for c in codes)
    assert migrated.execute("SELECT COUNT(*) FROM blood_units WHERE expiry_date < collected_at").fetchone()[0] == 0


def test_unsafe_or_invalid_rows_are_rejected_not_lost(migrated):
    rejected = rows(migrated, "SELECT source_table, reason FROM migration_rejects ORDER BY id")
    tables = [t for t, _ in rejected]
    assert tables.count("blood_units") == 3                      # bad group, no expiry, negative units
    assert tables.count("donors") == 2                           # duplicate CNIC, bad group
    assert {"blood_requests", "exchanges", "inventory_changes"} <= set(tables)
    # the original row is still readable from the reject table
    row = migrated.execute("SELECT row_json FROM migration_rejects WHERE source_table='blood_units' "
                           "AND row_json LIKE '%ZZ%'").fetchone()
    assert row is not None
    assert rows(migrated, "SELECT COUNT(*) FROM donors") == [(1,)]              # the first Ali survives
    assert rows(migrated, "SELECT COUNT(*) FROM blood_units WHERE blood_group IN ('ZZ','A-','B-')") == [(0,)]


def test_other_tables_and_legacy_data_are_carried_over(migrated):
    assert rows(migrated, "SELECT status, units_needed FROM blood_requests") == [("PENDING", 2)]
    assert rows(migrated, "SELECT blood_group, units FROM transfusions") == [("A+", 1)]
    assert rows(migrated, "SELECT status FROM exchanges") == [("PENDING",)]
    assert rows(migrated, "SELECT donor_id, result FROM screening_tests") == [(1, "PASS")]
    assert rows(migrated, "SELECT vendor_name FROM vendor_contracts_legacy") == [("Punjab Blood Service",)]
    assert rows(migrated, "SELECT COUNT(*) FROM contracts") == [(0,)]           # new lend/borrow table starts empty
    assert rows(migrated, "SELECT action_type, entity_type FROM audit_logs") == [("LOGIN", None)]


def test_inventory_deltas_become_one_event_per_unit(migrated):
    assert rows(migrated, "SELECT event_type, COUNT(*) FROM inventory_events GROUP BY 1 ORDER BY 1") == [
        ("issued", 2), ("received", 3)]
    assert "inventory_changes" not in {r[0] for r in migrated.execute("SELECT name FROM sqlite_master")}


def test_migrated_database_is_consistent_and_audit_is_append_only(migrated):
    assert migrated.execute("PRAGMA foreign_key_check").fetchall() == []
    assert migrated.execute("PRAGMA user_version").fetchone()[0] == 2
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        migrated.execute("UPDATE audit_logs SET description = 'tampered'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        migrated.execute("DELETE FROM audit_logs")


def test_fresh_schema_and_migrated_schema_have_the_same_shape(migrated):
    """schema.sql (fresh installs) and the migrations (existing installs) must never drift apart."""
    fresh = sqlite3.connect(":memory:")
    create_schema(fresh)

    def shape(conn):
        out = {}
        for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            if table in {"patients", "vendor_contracts_legacy"}:      # legacy tables kept only on migrated DBs
                continue
            out[table] = (
                [r[1:] for r in conn.execute(f"PRAGMA table_info({table})")],
                sorted((r[2], r[3], r[4]) for r in conn.execute(f"PRAGMA foreign_key_list({table})")),
                sorted((r[1], r[2], r[4]) for r in conn.execute(f"PRAGMA index_list({table})")
                       if not r[1].startswith("sqlite_")),
            )
        triggers = sorted(r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'"))
        return out, triggers

    assert shape(fresh) == shape(migrated)
    assert fresh.execute("PRAGMA user_version").fetchone()[0] == migrate.LATEST_VERSION
