"""What the AI Center actually sends to OpenRouter: patients pseudonymised, no PII in any payload."""
import sqlite3
import time

import pytest
import requests
import streamlit as st
from streamlit.testing.v1 import AppTest

from lifeline.config import get_settings
from lifeline.db.connection import connect
from lifeline.db.repositories import people

CNIC = "35202-1234567-1"
PHONE = "0300-1234567"


@pytest.fixture
def sent(monkeypatch, demo_db):
    """Enable AI with a fake key and capture every request body instead of calling the network."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-not-real")
    get_settings.cache_clear()
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)
    payloads: list[str] = []

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        payloads.append(str(json))
        return FakeResp()

    monkeypatch.setattr(requests, "post", fake_post)

    conn = sqlite3.connect(get_settings().db_path)
    conn.execute("INSERT INTO transfusions (hospital_id, patient_name, blood_group, units, transfused_at, performed_by, notes)"
                 " VALUES (1, 'Zubair Qadeer', 'A+', 2, '2026-06-01T10:00:00+05:00', 'Dr. Kamran Sheikh', ?)",
                 (f"Zubair Qadeer cnic {CNIC} phone {PHONE}",))
    conn.execute("INSERT INTO audit_logs (action_type, description, user_id, timestamp) VALUES"
                 " ('TRANSFUSION', 'Transfused 2u A+ to Zubair Qadeer', 1, '2026-06-01T10:00:00+05:00')")
    conn.commit()
    conn.close()
    return payloads


def secrets() -> list[str]:
    """Every real person name in the database, plus the identifiers planted above."""
    conn = connect()
    try:
        names = [n for n in people.person_names(conn) if len(n) >= 6]
    finally:
        conn.close()
    return [*names, CNIC, PHONE, "35202-1234567"]


def open_ai_center():
    at = AppTest.from_file("pages/9_ai_center.py", default_timeout=90)
    for k, v in dict(logged_in=True, user_id=1, user_email="a@x.pk", user_name="Admin", user_role="super_admin",
                     user_hospital_id=None, user_hospital_name="Global", last_active=time.time()).items():
        at.session_state[k] = v
    return at.run()


def click(at, label):
    next(b for b in at.button if b.label == label).click()
    return at.run()


def test_triage_payload_has_no_patient_names(sent):
    at = click(open_ai_center(), "AI Triage Analysis")
    assert not at.exception and sent, "the triage request should have been sent"
    body = " ".join(sent)
    assert "Patient 1" in body
    for secret in secrets():
        assert secret not in body, secret


def test_anomaly_payload_has_no_pii(sent):
    at = click(open_ai_center(), "Run Anomaly Scan")
    assert not at.exception and sent
    body = " ".join(sent)
    for secret in secrets():
        assert secret not in body, secret
    assert "TRANSFUSION" in body or "issued" in body      # the useful, non-identifying signal is still there


def test_chat_message_is_scrubbed_before_sending(sent):
    conn = connect()
    try:
        name = next(n for n in people.person_names(conn) if n.startswith("Zubair"))
    finally:
        conn.close()
    at = open_ai_center()
    at.session_state["chat_history"] = [{"role": "user", "content": f"Is {name} ({CNIC}) eligible?"}]
    at.run()
    body = " ".join(sent)
    assert sent and name not in body and "35202" not in body
    assert "[NAME]" in body and "[CNIC]" in body
