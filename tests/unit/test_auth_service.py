import sqlite3

import pytest

import setup_database
from lifeline.auth import passwords, service, session, throttle
from lifeline.auth.roles import Role
from lifeline.config import get_settings
from lifeline.demo import DEMO_PASSWORD

PASSWORD = "correct horse"


@pytest.fixture
def db():
    conn = sqlite3.connect(get_settings().db_path)
    setup_database.create_schema(conn)
    conn.execute("INSERT INTO hospitals (id, name, city) VALUES (1, 'Mayo', 'Lahore')")
    conn.execute(
        "INSERT INTO users (email, password_hash, role, name, created_at, hospital_id) VALUES (?,?,?,?,?,?)",
        ("nurse@x.pk", passwords.hash_password(PASSWORD), "staff", "Nurse", "t", 1),
    )
    conn.commit()
    yield conn
    conn.close()


def audit_actions(db):
    return [r[0] for r in db.execute("SELECT action_type FROM audit_logs ORDER BY id")]


def test_success_returns_user_without_hash_and_audits(db):
    result = service.authenticate("  Nurse@X.pk ", PASSWORD, now=1000)
    assert result.ok and result.user is not None
    assert "password_hash" not in result.user and result.user["role"] == "staff"
    assert audit_actions(db) == ["LOGIN"]


def test_failures_are_indistinguishable_for_unknown_and_wrong_password(db):
    unknown = service.authenticate("ghost@x.pk", "whatever1", now=1000)
    wrong = service.authenticate("nurse@x.pk", "whatever1", now=1000)
    assert not unknown.ok and not wrong.ok
    assert unknown.error == wrong.error == service.GENERIC_ERROR
    assert audit_actions(db) == ["LOGIN_FAILED", "LOGIN_FAILED"]


def test_lockout_after_max_attempts_then_expires(db):
    settings = get_settings()
    for i in range(settings.login_max_attempts):
        last = service.authenticate("nurse@x.pk", "bad-password", now=1000 + i)
    assert last.retry_after == settings.login_lockout_minutes * 60 and "Too many" in (last.error or "")
    assert "LOGIN_LOCKED" in audit_actions(db)

    # correct password is refused while locked, and does not extend the lock
    locked = service.authenticate("nurse@x.pk", PASSWORD, now=1100)
    assert not locked.ok and locked.retry_after > 0
    assert throttle.lock_remaining("nurse@x.pk", 1100) == locked.retry_after

    after = 1000 + settings.login_max_attempts + settings.login_lockout_minutes * 60 + 1
    assert service.authenticate("nurse@x.pk", PASSWORD, now=after).ok


def test_unknown_emails_are_throttled_too(db):
    for i in range(get_settings().login_max_attempts):
        service.authenticate("ghost@x.pk", "bad-password", now=2000 + i)
    assert throttle.lock_remaining("ghost@x.pk", 2010) > 0


def test_success_resets_the_failure_counter(db):
    for i in range(get_settings().login_max_attempts - 1):
        service.authenticate("nurse@x.pk", "bad-password", now=3000 + i)
    assert service.authenticate("nurse@x.pk", PASSWORD, now=3010).ok
    # a fresh full set of attempts is available again
    for i in range(get_settings().login_max_attempts - 1):
        assert service.authenticate("nurse@x.pk", "bad-password", now=3020 + i).retry_after == 0


def test_legacy_hash_is_upgraded_on_login(db):
    db.execute("UPDATE users SET password_hash = ?", (passwords.legacy_sha256(PASSWORD),))
    db.commit()
    assert service.authenticate("nurse@x.pk", PASSWORD, now=1).ok
    stored = db.execute("SELECT password_hash FROM users").fetchone()[0]
    assert stored.startswith("$2") and passwords.verify_password(PASSWORD, stored)


def test_known_legacy_demo_hashes_are_upgraded_in_bulk(db):
    db.execute("UPDATE users SET password_hash = ?", (passwords.legacy_sha256(DEMO_PASSWORD),))
    db.commit()
    assert service.upgrade_known_legacy_hashes([DEMO_PASSWORD]) == 1
    assert db.execute("SELECT password_hash FROM users").fetchone()[0].startswith("$2")
    assert service.upgrade_known_legacy_hashes([DEMO_PASSWORD]) == 0


@pytest.mark.parametrize(
    ("email", "name", "password", "role", "hospital", "fragment"),
    [
        ("not-an-email", "N", PASSWORD, "staff", 1, "valid email"),
        ("new@x.pk", " ", PASSWORD, "staff", 1, "name"),
        ("new@x.pk", "N", "short", "staff", 1, "at least"),
        ("new@x.pk", "N", PASSWORD, "admin", 1, "valid role"),          # the old, retired role name
        ("new@x.pk", "N", PASSWORD, "staff", None, "hospital"),
        ("nurse@x.pk", "N", PASSWORD, "staff", 1, "already exists"),
    ],
)
def test_create_user_rejections(db, email, name, password, role, hospital, fragment):
    ok, message = service.create_user(email, name, password, role, hospital, actor_id=None)
    assert not ok and fragment in message


def test_create_user_hashes_password_normalises_and_audits(db):
    ok, _ = service.create_user("New@X.pk", "New", PASSWORD, Role.SUPER_ADMIN.value, 1, actor_id=None)
    assert ok
    row = db.execute("SELECT email, role, hospital_id, password_hash FROM users WHERE email='new@x.pk'").fetchone()
    assert row[1] == "super_admin" and row[2] is None                  # global role is never tied to a hospital
    assert row[3].startswith("$2") and PASSWORD not in row[3]
    assert "USER_CREATED" in audit_actions(db)


def test_session_timeout_fails_closed(monkeypatch):
    fake: dict = {}
    monkeypatch.setattr(session.st, "session_state", fake, raising=False)
    assert session.is_expired()                                          # no activity stamp -> expired
    fake["last_active"] = 1000.0
    limit = get_settings().session_timeout_minutes * 60
    assert not session.is_expired(now=1000.0 + limit - 1)
    assert session.is_expired(now=1000.0 + limit + 1)


def test_session_logout_keeps_theme_and_sets_flash(db, monkeypatch):
    fake = {"logged_in": True, "user_id": 1, "user_email": "nurse@x.pk", "theme": "light", "secret": "x"}
    monkeypatch.setattr(session.st, "session_state", fake, raising=False)
    session.logout("bye", expired=True)
    assert fake == {"theme": "light", "_flash": "bye"}
    assert "SESSION_EXPIRED" in audit_actions(db)


def test_session_login_populates_the_flat_keys_pages_read(db, monkeypatch):
    fake: dict = {}
    monkeypatch.setattr(session.st, "session_state", fake, raising=False)
    user = service.authenticate("nurse@x.pk", PASSWORD, now=1).user
    assert user is not None
    current = session.login(user)
    assert current.role is Role.STAFF and current.hospital_name == "Mayo" and not current.is_super
    assert fake["logged_in"] is True and fake["user_role"] == "staff" and fake["user_hospital_id"] == 1
    assert fake["last_active"] > 0 and session.current_user() == current
    fake["user_role"] = "admin"                                   # retired name: no valid user any more
    assert session.current_user() is None


def test_session_login_for_global_user_has_no_hospital(db, monkeypatch):
    fake: dict = {}
    monkeypatch.setattr(session.st, "session_state", fake, raising=False)
    current = session.login({"id": 9, "email": "a@x.pk", "name": "A", "role": "super_admin", "hospital_id": None})
    assert current.is_super and current.hospital_id is None and "Global" in current.hospital_name


def test_create_admin_cli(db, monkeypatch, capsys):
    from lifeline.auth import create_admin

    answers = iter(["root@x.pk", "Root"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    passwords_typed = iter([PASSWORD, PASSWORD])
    monkeypatch.setattr(create_admin.getpass, "getpass", lambda _prompt="": next(passwords_typed))
    assert create_admin.main() == 0
    assert db.execute("SELECT role FROM users WHERE email='root@x.pk'").fetchone()[0] == "super_admin"


def test_create_admin_cli_rejects_mismatch_and_missing_db(db, monkeypatch, capsys):
    from lifeline.auth import create_admin

    answers = iter(["root@x.pk", "Root"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    typed = iter([PASSWORD, "different-one"])
    monkeypatch.setattr(create_admin.getpass, "getpass", lambda _prompt="": next(typed))
    assert create_admin.main() == 1
    assert "do not match" in capsys.readouterr().out


def test_create_admin_cli_without_database(monkeypatch, capsys):
    from lifeline.auth import create_admin

    assert create_admin.main() == 1
    assert "setup_database.py" in capsys.readouterr().out
