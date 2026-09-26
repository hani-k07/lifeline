"""Transfusion: the log, recording a transfusion (compatibility enforced) and the reaction monitor."""
from __future__ import annotations

import streamlit as st

from lifeline.auth.roles import Role
from lifeline.constants import BLOOD_GROUPS
from lifeline.engine.base import EngineError
from lifeline.engine.compatibility import compatible_donor_groups
from lifeline.engine.transfusion import fuzzy_severity, monitor_reaction
from lifeline.services.transfusion import record_transfusion
from lifeline.ui import components as ui
from lifeline.ui.layout import guard, page
from utils.actions import attempt
from utils.database import get_all_hospitals, get_blood_summary, get_transfusions

user = page(__file__, "Transfusion", "Record transfusions and watch for reactions")

with guard():
    if user.role is Role.SUPER_ADMIN:
        by_name = {h["name"]: h["id"] for h in get_all_hospitals()}
        hospital_id = by_name[st.selectbox("Hospital", list(by_name), key="tx_hosp")]
    else:
        hospital_id = user.hospital_id
    assert hospital_id is not None

    tab_log, tab_record, tab_monitor = st.tabs(["Log", "Record transfusion", "Reaction monitor"])

    with tab_log:
        rows = get_transfusions(hospital_id)
        ui.kpi_row(ui.kpi_card("Transfusions", len(rows)), ui.kpi_card("Units transfused", sum(r["units"] for r in rows)))
        ui.data_table(
            rows,
            [ui.Col("When", "transfused_at", render=lambda v, r: str(v)[:16].replace("T", " ")), ui.Col("Patient", "patient_name"),
             ui.Col("Patient group", "patient_blood_group", render=lambda v, r: ui.blood_group_badge(v) if v else "—"),
             ui.Col("Unit group", "blood_group", render=lambda v, r: ui.blood_group_badge(v)), ui.Col("Units", "units", align="right"),
             ui.Col("Performed by", "performed_by"), ui.Col("Notes", "notes", sortable=False)],
            key="tx_log", empty_title="No transfusions recorded", empty_body="Record one in the next tab.")

    with tab_record:
        ui.section_header("Record a transfusion", "compatibility and stock are checked before anything is saved")
        c1, c2, c3 = st.columns(3)
        patient_group = c1.selectbox("Patient blood group", BLOOD_GROUPS, key="tx_pgroup")
        compatible = compatible_donor_groups(patient_group)
        unit_group = c2.selectbox("Blood group of the units", BLOOD_GROUPS, index=BLOOD_GROUPS.index(patient_group), key="tx_ugroup")
        units = c3.number_input("Units", min_value=1, max_value=20, value=1, step=1, key="tx_units")
        ui.render(ui.Html("Compatible with this patient: " + " ".join(ui.blood_group_badge(g) for g in compatible)))
        patient = st.text_input("Patient name or reference", key="tx_patient")
        by = st.text_input("Performed by (physician or nurse)", key="tx_by")
        notes = st.text_area("Clinical notes (optional)", key="tx_notes", height=70)
        have = get_blood_summary(hospital_id).get(unit_group, 0)
        problem = None
        if unit_group not in compatible:
            problem = f"{unit_group} blood is NOT compatible with a {patient_group} patient. Choose a compatible group."
        elif int(units) > have:
            problem = f"Only {have} unit(s) of {unit_group} are in stock."
        ui.field_error(problem)
        if ui.confirm_dialog("tx", "Record transfusion",
                             f"Record {int(units)} × {unit_group} transfused to a {patient_group} patient? Units are removed from stock now.",
                             confirm_label="Yes, record", disabled=problem is not None or not patient.strip()):
            ok, error, _ = attempt(record_transfusion, user, hospital_id, patient, patient_group, unit_group, int(units), by, notes)
            if ok:
                st.toast("Transfusion recorded")
                st.rerun()
            ui.alert_banner(error or "Could not record the transfusion.", "danger")
        if not patient.strip():
            st.caption("Enter the patient's name or reference to enable recording.")

    with tab_monitor:
        ui.section_header("Reaction check", "enter vitals before and after the transfusion started")
        left, right = st.columns(2)
        with left:
            st.markdown("**Before**")
            pre_temp = st.number_input("Temperature (°C) before", 35.0, 42.0, 36.8, key="pre_temp")
            pre_bp = st.number_input("Systolic BP (mmHg) before", 60, 200, 120, key="pre_bp")
            pre_pulse = st.number_input("Pulse (bpm) before", 40, 180, 75, key="pre_pulse")
            pre_o2 = st.number_input("SpO₂ (%) before", 70.0, 100.0, 99.0, key="pre_o2")
        with right:
            st.markdown("**Now**")
            post_temp = st.number_input("Temperature (°C) now", 35.0, 42.0, 37.0, key="post_temp")
            post_bp = st.number_input("Systolic BP (mmHg) now", 60, 200, 118, key="post_bp")
            post_pulse = st.number_input("Pulse (bpm) now", 40, 180, 78, key="post_pulse")
            post_o2 = st.number_input("SpO₂ (%) now", 70.0, 100.0, 98.0, key="post_o2")
        if st.button("Check for a reaction", type="primary", key="mon_go"):
            try:
                result = monitor_reaction({"temp": pre_temp, "bp_systolic": pre_bp, "pulse": pre_pulse, "o2_sat": pre_o2},
                                          {"temp": post_temp, "bp_systolic": post_bp, "pulse": post_pulse, "o2_sat": post_o2})
            except EngineError as exc:
                ui.alert_banner(f"Check the entries: {exc}", "danger")
            else:
                severity = result["severity"]
                ui.kpi_row(ui.kpi_card("Severity", severity, tone={"red": "danger", "amber": "warning", "green": "success"}[result["alert_color"]]),
                           ui.kpi_card("Pattern", result["reaction_type"].replace("_", " ").title()))
                ui.alert_banner(result["action"], {"red": "danger", "amber": "warning", "green": "success"}[result["alert_color"]],
                                title="Recommended action")
                d = result["deltas"]
                if d:
                    st.caption(f"Changes: temperature {d['temp_rise']:+.1f} °C · systolic BP {-d['bp_drop']:+.0f} mmHg · "
                               f"pulse {d['pulse_rise']:+.0f} bpm · SpO₂ {d['o2_change']:+.1f} points")
                    fuzzy = fuzzy_severity(d["temp_rise"], d["bp_drop"], d["o2_drop"], d["pulse_rise"])
                    st.caption(f"Graded severity score (supplementary): {fuzzy['severity_score']}/100 · {fuzzy['severity_label']}")
                if result["fired_rules"]:
                    ui.section_header("Findings", "every rule that fired")
                    ui.render(ui.html_table(result["fired_rules"], [
                        ui.Col("Rule", "rule_name", render=lambda v, r: str(v).replace("_", " ")),
                        ui.Col("Severity", "severity", render=lambda v, r: ui.status_pill(v)), ui.Col("Reason", "reason")]))
                st.caption("Decision support only. The clinician makes every treatment decision. Thresholds are proposals awaiting clinical sign-off.")
