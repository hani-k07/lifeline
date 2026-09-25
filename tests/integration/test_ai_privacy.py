"""What the AI Center actually sends to OpenRouter: patients pseudonymised, no PII in any payload."""
import sqlite3
import time

import pytest
import requests
import streamlit as st
from streamlit.testing.v1 import AppTest

import setup_database
from lifeline.config import get_settings

SECRETS = ["Ali Hassan", "Maria Khan", "Usman Tariq", "35202-1234567-1", "0300-1234567", "Dr. Kamran Sheikh"]


@pytest.fixture
def sent(monkeypatch):
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
    setup_database.create_schema(conn)
    setup_database.seed_hospitals(conn)
    setup_database.seed_users(conn)
    setup_database.seed_blood_inventory(conn)
    setup_database.seed_sample_requests(conn)          # patients Ali Hassan, Maria Khan, Usman Tariq...
    conn.execute(
        "INSERT INTO transfusions (hospital_id, patient_name, blood_group, units, transfused_at, performed_by, notes)"
        " VALUES (1, 'Ali Hassan', 'A+', 2, '2026-06-01T10:00:00', 'Dr. Kamran Sheikh',"
        " 'Ali Hassan cnic 35202-1234567-1 phone 0300-1234567')"
    )
    conn.execute(
        "INSERT INTO audit_logs (action_type, description, user_id, timestamp) VALUES"
        " ('TRANSFUSION', 'Transfused 2u A+ to Ali Hassan', 1, '2026-06-01T10:00:00')"
    )
    conn.commit()
    conn.close()
    return payloads


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
    for secret in SECRETS:
        assert secret not in body, secret


def test_anomaly_payload_has_no_pii(sent):
    at = click(open_ai_center(), "Run Anomaly Scan")
    assert not at.exception and sent
    body = " ".join(sent)
    for secret in SECRETS:
        assert secret not in body, secret
    assert "TRANSFUSION" in body                       # the useful, non-identifying signal is still there


def test_chat_message_is_scrubbed_before_sending(sent):
    at = open_ai_center()
    at.session_state["chat_history"] = [{"role": "user", "content": "Is Usman Tariq (35202-1234567-1) eligible?"}]
    at.run()
    body = " ".join(sent)
    assert sent and "Usman Tariq" not in body and "35202" not in body
    assert "[NAME]" in body and "[CNIC]" in body
