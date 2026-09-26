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


def click(at, key):
    at.button(key=key).click()
    return at.run()


def confirm(at, key):
    """Click a two-step control: ask, then confirm."""
    return click(click(at, f"{key}:ask"), f"{key}:yes")


def db(sql, *args):
    conn = sqlite3.connect(get_settings().db_path)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def available(hospital, group):
    return db("SELECT COUNT(*) FROM blood_units WHERE hospital_id=? AND blood_group=? AND status='available'"
              " AND expiry_date >= date('now','+5 hours')", hospital, group)[0][0]


def page_text(at):
    return " ".join(m.value for m in at.markdown)


def errors(at):
    return [m.value for m in at.markdown if "ll-alert danger" in m.value]


def buttons(at):
    return {b.key: b for b in at.button}


# ------------------------------------------------------------------ inventory

def test_receiving_stock_creates_individual_units_and_an_audit_row():
    before = available(1, "A+")
    at = open_page("2_inventory")
    at.selectbox(key="rcv_group").set_value("A+")
    at.number_input(key="rcv_units").set_value(7)
    at = click(at, "rcv_go")
    assert not at.exception and not errors(at)
    assert available(1, "A+") == before + 7
    assert db("SELECT COUNT(*) FROM audit_logs WHERE action_type='STOCK_RECEIVED' AND user_id=2")[0][0] == 1


def test_receiving_an_already_expired_unit_is_blocked_before_submitting():
    from datetime import date, timedelta
    at = open_page("2_inventory")
    at.date_input(key="rcv_expiry").set_value(date.today() - timedelta(days=1))
    at = at.run()
    assert any("expiry date must be in the future" in e for e in errors(at)), errors(at)
    assert buttons(at)["rcv_go"].disabled


def test_issuing_more_than_exists_is_blocked_inline_and_nothing_is_issued():
    have = available(1, "A+")
    at = open_page("2_inventory")
    at.selectbox(key="iss_group").set_value("A+")
    at.number_input(key="iss_units").set_value(200)
    at = at.run()
    assert any(f"Only {have} unit(s)" in e for e in errors(at)), errors(at)
    assert buttons(at)["issue:ask"].disabled
    assert available(1, "A+") == have


def test_issuing_needs_a_confirmation_and_takes_the_earliest_expiry_first():
    have = available(1, "O+")
    earliest = db("SELECT unit_code FROM blood_units WHERE hospital_id=1 AND blood_group='O+' AND status='available'"
                  " AND expiry_date >= date('now','+5 hours') ORDER BY expiry_date, id LIMIT 1")[0][0]
    at = open_page("2_inventory")
    at.selectbox(key="iss_group").set_value("O+")
    at.number_input(key="iss_units").set_value(1)
    at = click(at.run(), "issue:ask")
    assert available(1, "O+") == have                                     # asking alone changes nothing
    at = click(at, "issue:yes")
    assert not at.exception and not errors(at)
    assert available(1, "O+") == have - 1
    assert db("SELECT status FROM blood_units WHERE unit_code = ?", earliest) == [("issued",)]


def test_discarding_a_unit_requires_a_known_code_and_a_reason():
    code = db("SELECT unit_code FROM blood_units WHERE hospital_id=1 AND status='available' LIMIT 1")[0][0]
    at = open_page("2_inventory")
    at.text_input(key="dsc_code").set_value("NOPE")
    at = at.run()
    assert any("No unit has that code" in e for e in errors(at))
    assert buttons(at)["discard:ask"].disabled
    at.text_input(key="dsc_code").set_value(code)
    at = at.run()
    assert buttons(at)["discard:ask"].disabled                             # still no reason
    at.text_input(key="dsc_reason").set_value("cold-chain break")
    at = confirm(at.run(), "discard")
    assert not at.exception and not errors(at)
    assert db("SELECT status FROM blood_units WHERE unit_code = ?", code) == [("discarded",)]


def test_a_unit_of_another_hospital_cannot_be_discarded_by_a_hospital_admin():
    other = db("SELECT unit_code FROM blood_units WHERE hospital_id=2 AND status='available' LIMIT 1")[0][0]
    at = open_page("2_inventory")
    at.text_input(key="dsc_code").set_value(other)
    at.text_input(key="dsc_reason").set_value("test")
    at = at.run()
    assert any("another hospital" in e for e in errors(at)), errors(at)
    assert buttons(at)["discard:ask"].disabled


# ------------------------------------------------------------------ emergency (three-step flow)

def emergency_to_sources(patient="Route Patient", group="A+", units=2):
    at = open_page("3_emergency")
    at.text_input(key="em_patient").set_value(patient)
    at.selectbox(key="em_group").set_value(group)
    at.number_input(key="em_units").set_value(units)
    return click(at.run(), "em_find")


def test_emergency_step_one_needs_a_patient_reference():
    before = db("SELECT COUNT(*) FROM blood_requests")[0][0]
    at = open_page("3_emergency")
    at = click(at, "em_find")
    assert not at.exception
    assert any("Enter the patient" in e for e in errors(at)), errors(at)
    assert db("SELECT COUNT(*) FROM blood_requests")[0][0] == before
    assert "em_next" not in buttons(at)                                     # still on step 1


def test_find_blood_offers_compatible_groups_ranked_exact_first():
    """Audit: routing used to match the exact blood group only (an O- unit never appeared for an A+ patient)."""
    at = emergency_to_sources()
    assert not at.exception, [e.value for e in at.exception]
    rows = at.session_state["em_flow"]["options"]
    assert rows and rows[0]["exact"] and rows[0]["unit_group"] == "A+"
    assert {r["unit_group"] for r in rows} <= {"A+", "A-", "O+", "O-"}         # never an incompatible group
    assert any(not r["exact"] for r in rows)
    assert [r["distance_km"] for r in rows if r["exact"]] == sorted(r["distance_km"] for r in rows if r["exact"])
    assert all(r["route"] for r in rows)
    assert db("SELECT COUNT(*) FROM blood_requests WHERE patient_name = 'Route Patient'")[0][0] == 0   # a search saves nothing


def test_confirming_the_plan_creates_the_request_and_reserves_the_units_together():
    before_requests = db("SELECT COUNT(*) FROM blood_requests")[0][0]
    at = emergency_to_sources(units=2)
    at = click(at, "em_next")
    assert "em_confirm" in buttons(at) and not at.exception
    assert db("SELECT COUNT(*) FROM blood_requests")[0][0] == before_requests        # nothing yet
    at = click(at, "em_confirm")
    assert not at.exception and not errors(at), errors(at)
    assert db("SELECT COUNT(*) FROM blood_requests")[0][0] == before_requests + 1
    rid, status, units = db("SELECT id, status, units_needed FROM blood_requests ORDER BY id DESC LIMIT 1")[0]
    assert (status, units) == ("RESERVED", 2)
    assert db("SELECT COUNT(*) FROM blood_units WHERE request_id = ? AND status = 'reserved'", rid)[0][0] == 2
    assert "Request #" in page_text(at) and str(rid) in page_text(at)


def test_a_reserved_request_can_be_dispatched_and_a_pending_one_cancelled():
    at = emergency_to_sources(units=1)
    at = click(click(at, "em_next"), "em_confirm")
    rid = db("SELECT id FROM blood_requests ORDER BY id DESC LIMIT 1")[0][0]
    at = confirm(open_page("3_emergency"), f"disp_{rid}")
    assert not at.exception and not errors(at), errors(at)
    assert db("SELECT status FROM blood_requests WHERE id = ?", rid) == [("RESOLVED",)]
    assert db("SELECT COUNT(*) FROM blood_units WHERE request_id = ? AND status = 'issued'", rid)[0][0] == 1


def test_cancelling_an_open_request_releases_its_units():
    at = emergency_to_sources(units=2)
    click(click(at, "em_next"), "em_confirm")
    rid = db("SELECT id FROM blood_requests ORDER BY id DESC LIMIT 1")[0][0]
    at = confirm(open_page("3_emergency"), f"cancel_{rid}")
    assert not at.exception and not errors(at), errors(at)
    assert db("SELECT status FROM blood_requests WHERE id = ?", rid) == [("CANCELLED",)]
    assert db("SELECT COUNT(*) FROM blood_units WHERE request_id = ? AND status = 'reserved'", rid)[0][0] == 0


def test_staff_can_see_open_requests_but_not_dispatch_them():
    at = emergency_to_sources(units=1)
    click(click(at, "em_next"), "em_confirm")
    rid = db("SELECT id FROM blood_requests ORDER BY id DESC LIMIT 1")[0][0]
    staff = open_page("3_emergency", role="staff")
    assert f"disp_{rid}:ask" not in buttons(staff) and f"cancel_{rid}:ask" not in buttons(staff)


# ------------------------------------------------------------------ transfusion

def test_incompatible_transfusion_is_blocked_in_the_ui():
    before = db("SELECT COUNT(*) FROM transfusions")[0][0]
    at = open_page("7_transfusion")
    at.selectbox(key="tx_pgroup").set_value("O-")                        # patient is O-
    at.selectbox(key="tx_ugroup").set_value("A+")                        # ...but A+ blood is chosen
    at.text_input(key="tx_patient").set_value("Test Patient")
    at = at.run()
    assert any("NOT compatible" in e for e in errors(at)), errors(at)
    assert buttons(at)["tx:ask"].disabled
    assert db("SELECT COUNT(*) FROM transfusions")[0][0] == before


def test_compatible_transfusion_consumes_stock_and_links_units():
    before = available(1, "O+")
    at = open_page("7_transfusion")
    at.selectbox(key="tx_pgroup").set_value("A+")
    at.selectbox(key="tx_ugroup").set_value("O+")                        # O+ is compatible with A+
    at.number_input(key="tx_units").set_value(2)
    at.text_input(key="tx_patient").set_value("Test Patient")
    at = confirm(at.run(), "tx")
    assert not at.exception and not errors(at), errors(at)
    assert available(1, "O+") == before - 2
    assert db("SELECT COUNT(*) FROM blood_units WHERE transfusion_id = (SELECT MAX(id) FROM transfusions)")[0][0] == 2


def test_reaction_monitor_flags_low_oxygen_as_critical():
    """Audit P0: SpO2 84 % used to be reported as 'NORMAL, transfusion proceeding normally'."""
    at = open_page("7_transfusion")
    at.number_input(key="post_o2").set_value(84.0)
    at = click(at, "mon_go")
    assert not at.exception
    page = page_text(at)
    assert "CRITICAL" in page and "STOP the transfusion" in page and "proceeding normally" not in page


def test_reaction_monitor_normal_readings_show_no_findings():
    at = click(open_page("7_transfusion"), "mon_go")
    page = page_text(at)
    assert "NONE" in page and "STOP" not in page


# ------------------------------------------------------------------ loans

def test_loan_moves_units_between_hospitals_and_can_be_returned():
    lender_before, borrower_before = available(1, "B+"), available(2, "B+")
    at = open_page("6_contracts")
    at.selectbox(key="loan_borrower").set_value("Services Hospital")
    at.selectbox(key="loan_group").set_value("B+")
    at.number_input(key="loan_units").set_value(3)
    at = confirm(at.run(), "loan_new")
    assert not at.exception and not errors(at), errors(at)
    assert available(1, "B+") == lender_before - 3 and available(2, "B+") == borrower_before + 3
    cid, status, units = db("SELECT id, status, units FROM contracts ORDER BY id DESC LIMIT 1")[0]
    assert (status, units) == ("ACTIVE", 3)
    at = confirm(open_page("6_contracts"), f"ret_{cid}")
    assert not at.exception and not errors(at), errors(at)
    assert db("SELECT status FROM contracts WHERE id = ?", cid) == [("RETURNED",)]
    assert available(1, "B+") == lender_before and available(2, "B+") == borrower_before


def test_staff_cannot_create_loans():
    at = open_page("6_contracts", role="staff")
    assert "loan_new:ask" not in buttons(at)
    assert "Staff cannot create loans" in page_text(at)


# ------------------------------------------------------------------ exchange

def test_exchange_request_accept_and_complete():
    at = open_page("4_exchange")
    at.selectbox(key="ex_group").set_value("A+")
    at = click(at, "ex_find")
    assert not at.exception, [e.value for e in at.exception]
    found = at.session_state["ex_found"]["rows"]
    assert found
    at.number_input(key="ex_ask").set_value(1)
    at = confirm(at.run(), "ex_req")
    assert not at.exception and not errors(at), errors(at)
    xid, supplier, group, status = db("SELECT id, from_hospital_id, blood_group, status FROM exchanges ORDER BY id DESC LIMIT 1")[0]
    assert status == "PENDING"
    supplier_page = open_page("4_exchange", hospital_id=supplier)
    supplier_page = confirm(supplier_page, f"acc_{xid}")
    assert not supplier_page.exception and not errors(supplier_page), errors(supplier_page)
    assert db("SELECT status FROM exchanges WHERE id = ?", xid) == [("ACCEPTED",)]
    assert db("SELECT COUNT(*) FROM blood_units WHERE exchange_id = ? AND status = 'reserved'", xid)[0][0] == 1
    done = confirm(open_page("4_exchange", hospital_id=supplier), f"done_{xid}")
    assert not done.exception and not errors(done), errors(done)
    assert db("SELECT status FROM exchanges WHERE id = ?", xid) == [("COMPLETED",)]
    assert db("SELECT hospital_id FROM blood_units WHERE exchange_id = ?", xid) == [(1,)]


def test_exchange_page_shows_network_suggestions_without_error():
    at = open_page("4_exchange", role="super_admin", hospital_id=None)
    assert not at.exception
    assert "Suggested transfers" in page_text(at)


# ------------------------------------------------------------------ donors and screening

def test_donor_registration_rejects_a_duplicate_cnic_and_masks_it_on_screen():
    at = open_page("5_screening")
    at.text_input(key="reg_name").set_value("New Donor")
    at.text_input(key="reg_cnic").set_value("35202-7654321-9")
    at = click(at.run(), "reg_go")
    assert not at.exception and not errors(at), errors(at)
    assert db("SELECT cnic FROM donors WHERE name='New Donor'") == [("35202-7654321-9",)]
    at = open_page("5_screening")
    page = page_text(at)
    assert "35202-7654321-9" not in page and "35202-*******-9" in page
    at.text_input(key="reg_name").set_value("Twin Donor")
    at.text_input(key="reg_cnic").set_value("3520276543219")
    at = click(at.run(), "reg_go")
    assert any("already registered" in e for e in errors(at)), errors(at)


def test_a_malformed_cnic_is_flagged_while_typing():
    at = open_page("5_screening")
    at.text_input(key="reg_cnic").set_value("35202-12")
    at = at.run()
    assert any("13 digits" in e for e in errors(at)), errors(at)


def test_screening_low_hemoglobin_is_deferred_and_the_donor_marked_ineligible():
    """Audit P0: this used to come back SAFE."""
    at = open_page("5_screening")
    picker = at.selectbox(key="scr_donor")
    donor_label = picker.options[0]
    picker.set_value(donor_label)
    at.number_input(key="scr_hb").set_value(9.0)
    at = click(at.run(), "scr_go")
    assert not at.exception, [e.value for e in at.exception]
    page = page_text(at)
    assert "DEFER" in page and "low hemoglobin" in page.lower()
    assert db("SELECT decision, risk_score FROM screening_tests ORDER BY id DESC LIMIT 1")[0][0] == "DEFER"
    donor_name = donor_label.rsplit(" (", 1)[0]
    assert db("SELECT eligible FROM donors WHERE name = ? AND hospital_id = 1", donor_name)[0][0] == 0


def test_screening_lists_every_rule_that_fired():
    at = open_page("5_screening")
    picker = at.selectbox(key="scr_donor")
    picker.set_value(picker.options[0])
    at.number_input(key="scr_hb").set_value(9.0)
    at.number_input(key="scr_temp").set_value(38.6)
    at.number_input(key="scr_pulse").set_value(120)
    at = click(at.run(), "scr_go")
    page = page_text(at).lower()
    for rule in ("low hemoglobin", "fever", "pulse out of range"):
        assert rule in page, rule


# ------------------------------------------------------------------ analytics

def test_analytics_uses_real_usage_and_shows_the_donor_segments():
    at = open_page("8_analytics", role="super_admin", hospital_id=None)
    assert not at.exception
    page = page_text(at)
    assert "Donor segments" in page and "Shortage outlook" in page
    assert "Core" in page or "Occasional" in page
