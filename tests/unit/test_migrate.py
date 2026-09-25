import sqlite3

import pytest

import setup_database
from lifeline.config import get_settings
from lifeline.db import migrate

LEGACY_USERS = """
CREATE TABLE hospitals (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin','hospital','staff')), name TEXT NOT NULL,
    created_at TEXT NOT NULL, hospital_id INTEGER REFERENCES hospitals(id));
CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id));
INSERT INTO hospitals VALUES (1, 'Mayo');
INSERT INTO users (email,password_hash,role,name,created_at,hospital_id) VALUES
  ('a@x.pk','h','admin','A','t',NULL), ('h@x.pk','h','hospital','H','t',1), ('s@x.pk','h','staff','S','t',1);
INSERT INTO audit_logs VALUES (1, 2);
"""


def _legacy_db():
    path = get_settings().db_path
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_USERS)
    conn.commit()
    conn.close()
    return path


def test_legacy_roles_are_migrated_and_data_kept():
    path = _legacy_db()
    assert migrate.ensure_schema() == [1]
    conn = sqlite3.connect(path)
    roles = dict(conn.execute("SELECT email, role FROM users").fetchall())
    assert roles == {"a@x.pk": "super_admin", "h@x.pk": "hospital_admin", "s@x.pk": "staff"}
    assert conn.execute("SELECT user_id FROM audit_logs").fetchone()[0] == 2   # FK target survived
    assert conn.execute("PRAGMA user_version").fetchone()[0] == migrate.LATEST_VERSION
    assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='login_throttle'").fetchone()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (email,password_hash,role,name,created_at) VALUES ('x','h','admin','X','t')"
        )


def test_first_migration_leaves_a_backup_of_the_original():
    path = _legacy_db()
    migrate.ensure_schema()
    backup = path.with_name(path.name + ".bak-v0")
    assert backup.exists()
    roles = {r[0] for r in sqlite3.connect(backup).execute("SELECT role FROM users")}
    assert roles == {"admin", "hospital", "staff"}            # untouched original
    migrate.ensure_schema()                                    # no second backup / no overwrite
    assert sorted(p.name for p in path.parent.glob("*.bak-*")) == [backup.name]


def test_migration_is_idempotent():
    _legacy_db()
    assert migrate.ensure_schema() == [1]
    assert migrate.ensure_schema() == []


def test_missing_database_is_reported():
    with pytest.raises(migrate.DatabaseNotInitialised):
        migrate.ensure_schema()


def test_fresh_schema_matches_migrated_schema():
    """Guards against setup_database.create_schema and the migrations drifting apart."""
    fresh = sqlite3.connect(":memory:")
    setup_database.create_schema(fresh)
    _legacy_db()
    migrate.ensure_schema()
    migrated = sqlite3.connect(get_settings().db_path)
    def cols(conn, table):
        return [r[1:] for r in conn.execute(f"PRAGMA table_info({table})")]

    for table in ("users", "login_throttle"):
        assert cols(fresh, table) == cols(migrated, table), table
    assert fresh.execute("PRAGMA user_version").fetchone()[0] == migrate.LATEST_VERSION
