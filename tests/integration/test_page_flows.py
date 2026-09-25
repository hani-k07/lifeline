"""Drive the real forms and check what ends up in the database (and what the user is told)."""
import sqlite3
import time

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from lifeline.config import get_settings


@pytest.fixture(autouse=True)
def env(monkeypatch, demo_db):
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)
    monkeypatch.setattr(st, "switch_page", lambda *a, **k: None)


def open_page(page, role="hospital_admin", hospital_id=1):
    at = AppTest.from_file(f"pages/{page}.py", default_timeout=90)
    for k, v in dict(logged_in=True, user_id=2, user_email="mayo@lifeline.com", user_name="Mayo Admin", user_role=role,
                     user_hospital_id=hospital_id, user_hospital_name="Mayo Hospital", last_active=time.time()).items():
        at.session_state[k] = v
    return at.run()


def widget(at, kind, label):
    return next(w for w in getattr(at, kind) if w.label == label)


def submit(at, label):
    next(b for b in at.button if b.label == label).click()
    return at.run()


def db(sql, *args):
    conn = sqlite3.connect(get_settings().db_path)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def available(hospital, group):
    return db("SELECT COUNT(*) FROM blood_units WHERE hospital_id=? AND blood_group=? AND status='available'"
              " AND expiry_date >= date('now','+5 hours')", hospital, group)[0][0]


def errors(at):
    return [m.value for m in at.markdown if "alert-banner" in m.value and "DANGER" in m.value]


def test_add_stock_creates_individual_units_and_an_audit_row():
    before = available(1, "A+")
    at = open_page("2_inventory")
    widget(at, "number_input", "Units to Add").set_value(7)
    at = submit(at, "Add to Inventory")
    assert not at.exception and not errors(at)
    assert available(1, "A+") == before + 7
    assert db("SELECT COUNT(*) FROM audit_logs WHERE action_type='STOCK_RECEIVED' AND user_id=2")[0][0] == 1


def test_consuming_more_than_exists_is_refused_with_a_clear_message():
    have = available(1, "A+")
    at = open_page("2_inventory")
    at.selectbox(key="con_bg").set_value("A+")
    widget(at, "number_input", "Units Consumed").set_value(200)
    at = submit(at, "Record Consumption")
    assert not at.exception
    assert any("available" in e and "needed" in e for e in errors(at)), errors(at)
    assert available(1, "A+") == have                                   # nothing was consumed


def test_incompatible_transfusion_is_blocked_in_the_ui():
    before = db("SELECT COUNT(*) FROM transfusions")[0][0]
    at = open_page("7_transfusion")
    at.selectbox(key="compat_bg").set_value("O-")                       # patient is O-
    at = at.run()
    at.selectbox(key="t_bg").set_value("A+")                            # ...but A+ blood is chosen
    widget(at, "text_input", "Patient Name *").set_value("Test Patient")
    at = submit(at, "Record Transfusion")
    assert any("NOT compatible" in e for e in errors(at)), errors(at)
    assert db("SELECT COUNT(*) FROM transfusions")[0][0] == before


def test_compatible_transfusion_consumes_stock_and_links_units():
    before = available(1, "O+")
    at = open_page("7_transfusion")
    at.selectbox(key="compat_bg").set_value("A+")
    at = at.run()
    at.selectbox(key="t_bg").set_value("O+")                            # O+ is compatible with A+
    widget(at, "text_input", "Patient Name *").set_value("Test Patient")
    widget(at, "number_input", "Units Transfused").set_value(2)
    at = submit(at, "Record Transfusion")
    assert not at.exception and not errors(at), errors(at)
    assert available(1, "O+") == before - 2
    assert db("SELECT COUNT(*) FROM blood_units WHERE transfusion_id = (SELECT MAX(id) FROM transfusions)")[0][0] == 2


def test_emergency_request_is_created_pending():
    before = db("SELECT COUNT(*) FROM blood_requests")[0][0]
    at = open_page("3_emergency")
    widget(at, "text_input", "Patient Name").set_value("Emergency Patient")
    at = submit(at, "Submit Emergency Request")
    assert not at.exception and not errors(at)
    assert db("SELECT COUNT(*) FROM blood_requests")[0][0] == before + 1
    assert db("SELECT status, requesting_hospital_id FROM blood_requests ORDER BY id DESC LIMIT 1") == [("PENDING", 1)]


def test_loan_moves_units_between_hospitals():
    lender_before, borrower_before = available(1, "B+"), available(2, "B+")
    at = open_page("6_contracts")
    widget(at, "selectbox", "Borrowing hospital").set_value("Services Hospital")
    at = at.run()
    widget(at, "number_input", "Units").set_value(3)
    # the blood group selectbox has the label "Blood Group"
    widget(at, "selectbox", "Blood Group").set_value("B+")
    at = submit(at, "Create Loan")
    assert not at.exception and not errors(at), errors(at)
    assert available(1, "B+") == lender_before - 3 and available(2, "B+") == borrower_before + 3
    assert db("SELECT status, units FROM contracts ORDER BY id DESC LIMIT 1") == [("ACTIVE", 3)]


def test_donor_registration_rejects_a_duplicate_cnic_and_masks_it_on_screen():
    at = open_page("5_screening")
    tab_inputs = {w.label: w for w in at.text_input}
    tab_inputs["Full Name *"].set_value("New Donor")
    tab_inputs["CNIC"].set_value("35202-7654321-9")
    at = submit(at, "Register Donor")
    assert not at.exception and not errors(at)
    assert db("SELECT cnic FROM donors WHERE name='New Donor'") == [("35202-7654321-9",)]
    at = open_page("5_screening")
    page_html = " ".join(m.value for m in at.markdown)
    assert "35202-7654321-9" not in page_html and "35202-*******-9" in page_html
    tab_inputs = {w.label: w for w in at.text_input}
    tab_inputs["Full Name *"].set_value("Twin Donor")
    tab_inputs["CNIC"].set_value("3520276543219")
    at = submit(at, "Register Donor")
    assert any("already registered" in e for e in errors(at)), errors(at)


# ------------------------------------------------------------------ Phase 3: engine behaviour through the pages

def test_screening_low_hemoglobin_is_deferred_and_the_donor_marked_ineligible():
    """Audit P0: this used to come back SAFE."""
    at = open_page("5_screening")
    picker = widget(at, "selectbox", "Select Donor")
    donor_label = picker.options[0]
    picker.set_value(donor_label)
    widget(at, "number_input", "Hemoglobin (g/dL)").set_value(9.0)
    at = submit(at, "Run Screening")
    assert not at.exception
    page = " ".join(m.value for m in at.markdown)
    assert "DEFER" in page and "Low Hemoglobin" in page
    assert db("SELECT decision, risk_score FROM screening_tests ORDER BY id DESC LIMIT 1")[0][0] == "DEFER"
    donor_name = donor_label.rsplit(" (", 1)[0]
    assert db("SELECT eligible FROM donors WHERE name = ? AND hospital_id = 1", donor_name)[0][0] == 0


def test_screening_lists_every_rule_that_fired():
    at = open_page("5_screening")
    picker = widget(at, "selectbox", "Select Donor")
    picker.set_value(picker.options[0])
    widget(at, "number_input", "Hemoglobin (g/dL)").set_value(9.0)
    widget(at, "number_input", "Temperature (°C)").set_value(38.6)
    widget(at, "number_input", "Pulse (bpm)").set_value(120)
    at = submit(at, "Run Screening")
    page = " ".join(m.value for m in at.markdown)
    for rule in ("Low Hemoglobin", "Fever", "Pulse Out Of Range"):
        assert rule in page, rule


def test_reaction_monitor_flags_low_oxygen_as_critical():
    """Audit P0: SpO2 84 % used to be reported as 'NORMAL, transfusion proceeding normally'."""
    at = open_page("7_transfusion")
    at.number_input(key="post_o2").set_value(84.0)
    at = submit(at, "Analyse Reaction")
    assert not at.exception
    page = " ".join(m.value for m in at.markdown)
    assert "CRITICAL" in page and "STOP the transfusion" in page and "proceeding normally" not in page


def test_reaction_monitor_normal_readings_show_no_findings():
    at = open_page("7_transfusion")
    at = submit(at, "Analyse Reaction")
    page = " ".join(m.value for m in at.markdown)
    assert "NONE" in page and "STOP" not in page


def test_find_blood_offers_compatible_groups_and_reserves_them():
    """Audit: routing used to match the exact blood group only (an O- unit never appeared for an A+ patient)."""
    at = open_page("3_emergency")
    widget(at, "text_input", "Patient Name").set_value("Route Patient")
    at = submit(at, "Submit Emergency Request")
    at.selectbox(key="find_bg").set_value("A+")
    at = submit(at.run(), "Find Nearest Blood Source")
    rows = at.session_state["em_results"]["rows"]
    assert rows and rows[0]["exact"] and rows[0]["unit_group"] == "A+"
    assert {r["unit_group"] for r in rows} <= {"A+", "A-", "O+", "O-"}          # never an incompatible group
    assert any(not r["exact"] for r in rows)                                       # compatible substitutes are offered too
    assert [r["distance_km"] for r in rows if r["exact"]] == sorted(r["distance_km"] for r in rows if r["exact"])
    assert all(r["route"] for r in rows)


def test_analytics_uses_real_usage_and_shows_the_donor_segments():
    at = open_page("8_analytics", role="super_admin", hospital_id=None)
    assert not at.exception
    page = " ".join(m.value for m in at.markdown)
    assert "Donor segments" in page and "Shortage outlook" in page
    assert "Core" in page or "Occasional" in page


def test_exchange_page_shows_network_suggestions_without_error():
    at = open_page("4_exchange", role="super_admin", hospital_id=None)
    assert not at.exception
    assert any("Suggested transfers" in m.value for m in at.markdown)
