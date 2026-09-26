"""The sign-in page and the admin console, driven through the real widgets."""
import sqlite3
import time

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from lifeline.config import get_settings
from lifeline.demo import DEMO_PASSWORD


@pytest.fixture(autouse=True)
def switches(monkeypatch, demo_db):
    targets: list[str] = []
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)
    monkeypatch.setattr(st, "switch_page", lambda page, *a, **k: targets.append(page))
    return targets


def submit(at):
    next(b for b in at.button if b.label == "Sign in").click()
    return at.run()


def login_page():
    return AppTest.from_file("app.py", default_timeout=90).run()


def admin_page(role="super_admin"):
    at = AppTest.from_file("pages/10_admin.py", default_timeout=90)
    for k, v in dict(logged_in=True, user_id=1, user_email="admin@lifeline.com", user_name="Admin", user_role=role,
                     user_hospital_id=None, user_hospital_name="Global", last_active=time.time()).items():
        at.session_state[k] = v
    return at.run()


def text(at):
    return " ".join(m.value for m in at.markdown)


def db(sql, *args):
    conn = sqlite3.connect(get_settings().db_path)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


# ------------------------------------------------------------------ sign-in

def test_login_page_renders_and_hides_the_demo_accounts_outside_demo_mode(switches):
    at = login_page()
    assert not at.exception
    assert any(b.label == "Sign in" for b in at.button)
    assert "Demo accounts" not in text(at) and DEMO_PASSWORD not in text(at)


def test_demo_accounts_are_listed_only_when_the_environment_says_demo(switches, monkeypatch):
    monkeypatch.setenv("APP_ENV", "demo")
    get_settings.cache_clear()
    at = login_page()
    assert "Demo accounts" in text(at) and "admin@lifeline.com" in text(at) and DEMO_PASSWORD in text(at)


def test_wrong_credentials_show_one_generic_error_and_do_not_sign_in(switches):
    at = login_page()
    at.text_input(key="li_email").set_value("admin@lifeline.com")
    at.text_input(key="li_password").set_value("wrong-password")
    at = submit(at)
    assert not at.exception
    assert "Sign in failed" in text(at)
    assert "logged_in" not in at.session_state or not at.session_state["logged_in"]
    assert switches == []


def test_empty_form_asks_for_both_fields(switches):
    at = login_page()
    assert "Enter your email and password" in text(submit(at))


def test_correct_credentials_sign_in_and_go_to_the_dashboard(switches, monkeypatch):
    monkeypatch.setenv("APP_ENV", "demo")
    get_settings.cache_clear()
    at = login_page()
    at.text_input(key="li_email").set_value("mayo@lifeline.com")
    at.text_input(key="li_password").set_value(DEMO_PASSWORD)
    at = submit(at)
    assert not at.exception
    assert switches == ["pages/1_dashboard.py"]
    assert at.session_state["user_role"] == "hospital_admin" and at.session_state["user_hospital_id"] == 1


def test_theme_toggle_flips_the_theme(switches):
    at = login_page()
    at.button(key="li_theme").click()
    at = at.run()
    assert at.session_state["theme"] == "light"


# ------------------------------------------------------------------ admin console

def test_creating_a_user_validates_inline_then_saves_and_audits():
    at = admin_page()
    at.text_input(key="nu_email").set_value("not-an-email")
    at.text_input(key="nu_pw").set_value("short")
    at = at.run()
    page = text(at)
    assert "does not look like an email" in page and "at least 8 characters" in page
    at.text_input(key="nu_name").set_value("New Nurse")
    at = at.button(key="nu_go").click().run()
    assert db("SELECT COUNT(*) FROM users WHERE name = 'New Nurse'")[0][0] == 0         # nothing saved while invalid

    at.text_input(key="nu_email").set_value("nurse.new@lifeline.com")
    at.text_input(key="nu_pw").set_value("a-long-enough-pass")
    at.selectbox(key="nu_role").set_value("staff")
    at.selectbox(key="nu_hosp").set_value("Services Hospital")
    at = at.run()
    at = at.button(key="nu_go").click().run()
    assert not at.exception
    assert db("SELECT role, hospital_id FROM users WHERE email = 'nurse.new@lifeline.com'") == [("staff", 2)]
    assert db("SELECT COUNT(*) FROM audit_logs WHERE action_type = 'USER_CREATED'")[0][0] == 1
    stored = db("SELECT password_hash FROM users WHERE email = 'nurse.new@lifeline.com'")[0][0]
    assert stored.startswith("$2") and "a-long-enough-pass" not in stored              # bcrypt, never plain text


def test_a_duplicate_email_is_reported_not_crashed():
    at = admin_page()
    at.text_input(key="nu_email").set_value("mayo@lifeline.com")
    at.text_input(key="nu_name").set_value("Twin")
    at.text_input(key="nu_pw").set_value("a-long-enough-pass")
    at = at.run()
    at = at.button(key="nu_go").click().run()
    assert not at.exception and "already exists" in text(at)


def test_self_test_runs_from_the_admin_console_and_reports_healthy():
    at = admin_page()
    assert "Not run yet" in text(at)
    at = at.button(key="st_run").click().run()
    assert not at.exception, [e.value for e in at.exception]
    page = text(at)
    assert "Every check passed" in page and "Failed" in page


def test_the_audit_tab_notes_that_the_log_is_append_only():
    assert any("append-only" in c.value for c in admin_page().caption)


def test_staff_and_hospital_admins_cannot_open_the_admin_console():
    for role in ("staff", "hospital_admin"):
        at = admin_page(role)
        assert any("Access denied" in e.value for e in at.error), role
