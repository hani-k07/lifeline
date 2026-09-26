"""Load real pages through Streamlit's AppTest against a temporary seeded database."""
import sqlite3
import time

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from lifeline.config import ROOT, get_settings

PAGES = ["1_dashboard", "2_inventory", "3_emergency", "4_exchange", "5_screening",
         "6_contracts", "7_transfusion", "8_analytics", "9_ai_center", "10_admin"]
ALLOWED = {
    "super_admin": set(PAGES),
    "hospital_admin": set(PAGES) - {"10_admin"},
    "staff": set(PAGES) - {"10_admin", "9_ai_center"},
}


@pytest.fixture(autouse=True)
def switches(monkeypatch, demo_db):
    """AppTest has no multipage context: stub page_link and record switch_page targets instead."""
    targets: list[str] = []
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)
    monkeypatch.setattr(st, "switch_page", lambda page, *a, **k: targets.append(page))
    return targets


def run_page(page, role, *, hospital_id="default", last_active=None):
    at = AppTest.from_file(str(ROOT / f"pages/{page}.py"), default_timeout=90)
    if role is not None:
        if hospital_id == "default":
            hospital_id = None if role == "super_admin" else 1
        at.session_state["logged_in"] = True
        at.session_state["user_id"] = 1
        at.session_state["user_email"] = "t@x.pk"
        at.session_state["user_name"] = "Tester"
        at.session_state["user_role"] = role
        at.session_state["user_hospital_id"] = hospital_id
        at.session_state["user_hospital_name"] = "Mayo Hospital"
        at.session_state["last_active"] = time.time() if last_active is None else last_active
    return at.run()


@pytest.mark.parametrize("role", list(ALLOWED))
@pytest.mark.parametrize("page", PAGES)
def test_every_page_for_every_role(page, role):
    at = run_page(page, role)
    denied = any("Access denied" in e.value for e in at.error)
    assert not at.exception, [e.value for e in at.exception]
    assert denied is (page not in ALLOWED[role])


def test_denied_access_is_audited():
    run_page("10_admin", "staff")
    conn = sqlite3.connect(get_settings().db_path)
    actions = [r[0] for r in conn.execute("SELECT action_type FROM audit_logs")]
    assert "ACCESS_DENIED" in actions


def test_retired_role_names_are_bounced_to_login(switches):
    for legacy in ("admin", "hospital"):
        switches.clear()
        at = run_page("1_dashboard", legacy)
        assert not at.exception
        assert switches == ["app.py"]
        assert not at.markdown                                  # nothing of the dashboard was rendered


def test_hospital_scoped_user_without_hospital_is_refused():
    at = run_page("2_inventory", "staff", hospital_id=None)
    assert any("not assigned to a hospital" in e.value for e in at.error)


def test_visitor_without_session_is_sent_to_login(switches):
    assert not run_page("1_dashboard", None).exception
    assert switches == ["app.py"]


def test_idle_session_is_expired_and_cleared(switches):
    at = run_page("1_dashboard", "staff", last_active=time.time() - 3 * 3600)
    assert not at.exception
    assert switches == ["app.py"]
    assert "logged_in" not in at.session_state                 # logout() cleared it
    assert "expired" in at.session_state["_flash"]
    conn = sqlite3.connect(get_settings().db_path)
    assert "SESSION_EXPIRED" in [r[0] for r in conn.execute("SELECT action_type FROM audit_logs")]
