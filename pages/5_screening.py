"""Donors: registry, registration, and the screening test (every rule evaluated, every reason shown)."""
from __future__ import annotations

from datetime import date

import streamlit as st

from lifeline import clock
from lifeline.auth.roles import Role
from lifeline.constants import BLOOD_GROUPS
from lifeline.engine.base import EngineError
from lifeline.engine.screening import risk_score, screen_donor
from lifeline.errors import ValidationError
from lifeline.privacy import mask_cnic
from lifeline.services.donors import normalize_cnic, record_screening, register_donor
from lifeline.ui import components as ui
from lifeline.ui.layout import guard, page
from utils.actions import attempt
from utils.database import get_all_hospitals, get_donors, get_screening_tests

user = page(__file__, "Donors & screening", "Register donors and screen them before every donation")

with guard():
    if user.role is Role.SUPER_ADMIN:
        by_name = {h["name"]: h["id"] for h in get_all_hospitals()}
        hospital_id = by_name[st.selectbox("Hospital", list(by_name), key="don_hosp")]
    else:
        hospital_id = user.hospital_id
    assert hospital_id is not None

    tab_registry, tab_register, tab_screen = st.tabs(["Donor registry", "Register donor", "Screen a donor"])
    donors = get_donors(hospital_id)

    with tab_registry:
        tests = get_screening_tests(hospital_id)
        ui.kpi_row(ui.kpi_card("Registered donors", len(donors)),
                   ui.kpi_card("Eligible", sum(1 for d in donors if d["eligible"]), tone="success"),
                   ui.kpi_card("Deferred or blocked", sum(1 for d in donors if not d["eligible"]),
                               tone="warning" if any(not d["eligible"] for d in donors) else "neutral"),
                   ui.kpi_card("Screenings on record", len(tests)))
        ui.data_table(
            donors,
            [ui.Col("Name", "name"), ui.Col("Group", "blood_group", render=lambda v, r: ui.blood_group_badge(v)),
             ui.Col("CNIC", "cnic", render=lambda v, r: mask_cnic(v), search=False), ui.Col("Phone", "phone"),
             ui.Col("Age", "age", align="right"), ui.Col("Donations", "times_donated", align="right"),
             ui.Col("Last donated", "last_donated", render=lambda v, r: str(v or "never")[:10]),
             ui.Col("Eligibility", "eligible", render=lambda v, r: ui.status_pill("eligible" if v else "deferred",
                                                                                 kind="success" if v else "warning"))],
            key="don_reg", page_size=10, empty_title="No donors registered yet", empty_body="Add the first donor in the next tab.")

    with tab_register:
        ui.section_header("New donor")
        c1, c2 = st.columns(2)
        name = c1.text_input("Full name", key="reg_name")
        group = c2.selectbox("Blood group", BLOOD_GROUPS, key="reg_group")
        cnic = c1.text_input("CNIC (optional)", key="reg_cnic", placeholder="35202-1234567-1",
                             help="13 digits. Stored securely and shown masked.")
        phone = c2.text_input("Phone (optional)", key="reg_phone", placeholder="0300-1234567")
        age = c1.number_input("Age", min_value=16, max_value=100, value=30, step=1, key="reg_age")
        last = c2.date_input("Last donation (leave empty if never)", value=None, max_value=clock.today(), key="reg_last")
        notes = st.text_area("Medical notes (optional)", key="reg_notes", height=70)
        problems: dict[str, str] = {}
        try:
            normalize_cnic(cnic)
        except ValidationError as exc:
            problems["cnic"] = str(exc)
        ui.field_error(problems.get("cnic"))
        submitted = st.button("Register donor", type="primary", key="reg_go")
        if submitted:
            if not name.strip():
                ui.field_error("Enter the donor's full name.")
            elif problems:
                pass
            else:
                ok, error, _ = attempt(register_donor, user, hospital_id, name, group, cnic=cnic, phone=phone, age=int(age),
                                       last_donated=last, notes=notes)
                if ok:
                    st.toast(f"Donor {name.strip()} registered")
                    st.rerun()
                ui.alert_banner(error or "Could not register the donor.", "danger")

    with tab_screen:
        if not donors:
            ui.empty_state("No donors to screen", "Register a donor first.", icon="○")
        else:
            labels = {f"{d['name']} ({d['blood_group']})": d for d in donors}
            donor = labels[st.selectbox("Donor", list(labels), key="scr_donor")]
            ui.section_header("Serology")
            cols = st.columns(5)
            hiv, hepb, hepc = cols[0].checkbox("HIV", key="scr_hiv"), cols[1].checkbox("Hepatitis B", key="scr_hepb"), cols[2].checkbox("Hepatitis C", key="scr_hepc")
            syphilis, malaria = cols[3].checkbox("Syphilis", key="scr_syph"), cols[4].checkbox("Malaria", key="scr_mal")
            ui.section_header("Vitals", "every value is required to clear a donor")
            v1, v2, v3, v4 = st.columns(4)
            age = v1.number_input("Age", 10, 100, int(donor.get("age") or 30), key="scr_age")
            weight = v2.number_input("Weight (kg)", 25.0, 200.0, 65.0, key="scr_weight")
            hemoglobin = v3.number_input("Hemoglobin (g/dL)", 5.0, 20.0, 14.0, key="scr_hb")
            temperature = v4.number_input("Temperature (°C)", 34.0, 42.0, 36.8, key="scr_temp")
            v5, v6, v7, v8 = st.columns(4)
            bp_sys = v5.number_input("BP Systolic (mmHg)", 60, 260, 120, key="scr_sys")
            bp_dia = v6.number_input("BP Diastolic (mmHg)", 30, 160, 80, key="scr_dia")
            pulse = v7.number_input("Pulse (bpm)", 30, 200, 72, key="scr_pulse")
            thinners = v8.checkbox("On blood thinners", key="scr_thin")
            days_since = None
            if donor.get("last_donated"):
                days_since = max(0, (clock.today() - date.fromisoformat(str(donor["last_donated"])[:10])).days)
            st.caption("Days since last donation: " + ("never donated" if days_since is None else f"{days_since} (from the donor record)"))

            if st.button("Run screening", type="primary", key="scr_go"):
                data = {"age": age, "weight": weight, "hemoglobin": hemoglobin, "bp_systolic": bp_sys, "bp_diastolic": bp_dia,
                        "pulse": pulse, "temperature": temperature, "last_donation_days": days_since, "on_blood_thinners": thinners,
                        "hiv": hiv, "hepb": hepb, "hepc": hepc, "syphilis": syphilis, "malaria": malaria}
                try:
                    result, risk = screen_donor(data), risk_score(data)
                except EngineError as exc:
                    ui.alert_banner(f"Check the entries: {exc}", "danger")
                else:
                    ok, error, _ = attempt(record_screening, user, donor["id"], hospital_id, hiv=hiv, hepatitis_b=hepb,
                                           hepatitis_c=hepc, syphilis=syphilis, malaria=malaria, decision=result["decision"],
                                           risk_score=int(risk["score"]))
                    if not ok:
                        ui.alert_banner(error or "The result could not be saved.", "danger")
                    decision = result["decision"]
                    ui.kpi_row(ui.kpi_card("Decision", decision, tone={"SAFE": "success", "DEFER": "warning", "BLOCK": "danger"}[decision]),
                               ui.kpi_card("Risk score", f"{risk['score']}/100"))
                    ui.alert_banner(risk["recommendation"], {"SAFE": "success", "DEFER": "warning", "BLOCK": "danger"}[decision])
                    if result["fired_rules"]:
                        ui.section_header("Why", "every rule that fired")
                        ui.render(ui.html_table(result["fired_rules"], [
                            ui.Col("Rule", "rule_name", render=lambda v, r: str(v).replace("_", " ")),
                            ui.Col("Outcome", "decision", render=lambda v, r: ui.status_pill(v)), ui.Col("Reason", "reason")]))
                    with st.expander("Full inference trace"):
                        for line in result["inference_chain"]:
                            st.markdown(f"- {line}")
                    st.caption("Decision support only: thresholds are proposals awaiting clinical sign-off (docs/CLINICAL_REFERENCE.md).")
