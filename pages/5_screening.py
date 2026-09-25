# pages/5_screening.py
"""Donor Screening — LIFELINE v6.0"""
from __future__ import annotations

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Screening — LIFELINE", layout="wide")

from utils.styles import (
    inject_all_styles, get_theme, section_header, alert_banner,
    blood_badge, status_pill, styled_table, metric_card,
)
from lifeline.auth.rbac import require_page
from lifeline.privacy import mask_cnic
from lifeline.auth.roles import Role
from utils.sidebar import render_sidebar
from lifeline.services.donors import record_screening, register_donor
from utils.actions import attempt
from utils.database import get_all_hospitals, get_donors, get_screening_tests
from datetime import date

from lifeline import clock
from lifeline.constants import BLOOD_GROUPS
from lifeline.engine.base import EngineError
from lifeline.engine.screening import risk_score, screen_donor

user = require_page(__file__)

inject_all_styles(get_theme())
render_sidebar()

_role = st.session_state.get("user_role", "")
_hosp_id = st.session_state.get("user_hospital_id")
_uid = int(st.session_state.get("user_id", 0))
_hosp_name = st.session_state.get("user_hospital_name", "")

# ── Title Block ──
st.markdown("""
<div style="margin-bottom:24px">
    <h1 style="font-family:'Syne',sans-serif;font-size:1.6rem;margin:0">Donor Screening</h1>
    <p style="color:var(--text-secondary);font-size:0.82rem;margin:4px 0 0">
        Register donors and conduct pre-donation screening tests
    </p>
</div>""", unsafe_allow_html=True)

if _role == Role.SUPER_ADMIN:
    hospitals = get_all_hospitals()
    hosp_map = {h["name"]: h["id"] for h in hospitals}
    sel_name = st.selectbox("Hospital", list(hosp_map.keys()))
    sel_hosp_id = hosp_map[sel_name]
else:
    sel_hosp_id = _hosp_id
    sel_name = _hosp_name

tab1, tab2, tab3 = st.tabs(["Donor Registry", "Register Donor", "Screening Test"])

with tab1:
    donors = get_donors(sel_hosp_id)
    tests = get_screening_tests(sel_hosp_id)

    # 3-column metric cards
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(metric_card("Total Donors", f"{len(donors)}", icon="Donors", variant="default"), unsafe_allow_html=True)
    with c2:
        eligible_count = len([d for d in donors if d.get("eligible") == 1])
        st.markdown(metric_card("Eligible Donors", f"{eligible_count}", icon="Eligible", variant="success"), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Screening Tests", f"{len(tests)}", icon="Tests", variant="default"), unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    if donors:
        registry_rows = []
        for d in donors:
            registry_rows.append({
                "Name": d.get("name", "—"),
                "Blood Group": blood_badge(d.get("blood_group", "?")),
                "CNIC": mask_cnic(d.get("cnic")),
                "Phone": d.get("phone", "—"),
                "Last Donated": d.get("last_donated", "—"),
                "Eligible": status_pill("ACTIVE" if d.get("eligible") == 1 else "EXPIRED")
            })
        df_show = pd.DataFrame(registry_rows)
        styled_table(df_show)
    else:
        alert_banner("No donors registered yet.", "info")

with tab2:
    section_header("Register New Donor")
    
    error_msg = None

    with st.form("donor_form"):
        col1, col2 = st.columns(2)
        with col1:
            d_name = st.text_input("Full Name *")
            d_cnic = st.text_input("CNIC", placeholder="35202-XXXXXXX-X")
            d_phone = st.text_input("Phone", placeholder="0300-XXXXXXX")
        with col2:
            d_bg = st.selectbox("Blood Group *", BLOOD_GROUPS)
            d_age = st.number_input("Age", min_value=16, max_value=100, value=30)
            d_last = st.date_input("Last Donation Date (if any)", value=None)
            d_notes = st.text_area("Medical Notes", placeholder="Any conditions, medications...")

        if st.form_submit_button("Register Donor", use_container_width=True):
            ok, error_msg, _ = attempt(register_donor, user, sel_hosp_id, d_name, d_bg, cnic=d_cnic, phone=d_phone,
                                       age=int(d_age), last_donated=d_last, notes=d_notes)
            if ok:
                st.toast(f"Donor {d_name} registered")
                st.rerun()

    if error_msg:
        alert_banner(error_msg, "danger")

with tab3:
    section_header("Donor Screening Test", "Rule engine: every rule is evaluated and every reason is shown")

    donors = get_donors(sel_hosp_id)
    if not donors:
        alert_banner("No donors registered. Register a donor first.", "warning")
    else:
        donor_map = {f"{d['name']} ({d['blood_group']})": d for d in donors}
        donor = donor_map[st.selectbox("Select Donor", list(donor_map.keys()))]

        st.markdown("**Serology Panel:**")
        cols = st.columns(5)
        hiv = cols[0].checkbox("HIV")
        hep_b = cols[1].checkbox("Hepatitis B")
        hep_c = cols[2].checkbox("Hepatitis C")
        syphilis = cols[3].checkbox("Syphilis")
        malaria = cols[4].checkbox("Malaria")

        st.markdown("**Donor Vitals (all are required to clear a donor):**")
        v1, v2, v3, v4 = st.columns(4)
        age = v1.number_input("Age", 10, 100, int(donor.get("age") or 30))
        weight = v2.number_input("Weight (kg)", 25.0, 200.0, 65.0)
        hemoglobin = v3.number_input("Hemoglobin (g/dL)", 5.0, 20.0, 14.0)
        temperature = v4.number_input("Temperature (°C)", 34.0, 42.0, 36.8)
        v5, v6, v7, v8 = st.columns(4)
        bp_sys = v5.number_input("BP Systolic (mmHg)", 60, 260, 120)
        bp_dia = v6.number_input("BP Diastolic (mmHg)", 30, 160, 80)
        pulse = v7.number_input("Pulse (bpm)", 30, 200, 72)
        thinners = v8.checkbox("On blood thinners")

        days_since = None
        if donor.get("last_donated"):
            days_since = max(0, (clock.today() - date.fromisoformat(str(donor["last_donated"])[:10])).days)
        st.caption("Days since last donation: " + ("never donated" if days_since is None else f"{days_since} (from the donor record)"))

        if st.button("Run Screening", use_container_width=True):
            donor_data = {
                "age": age, "weight": weight, "hemoglobin": hemoglobin, "bp_systolic": bp_sys, "bp_diastolic": bp_dia,
                "pulse": pulse, "temperature": temperature, "last_donation_days": days_since, "on_blood_thinners": thinners,
                "hiv": hiv, "hepb": hep_b, "hepc": hep_c, "syphilis": syphilis, "malaria": malaria,
            }
            try:
                screen_result = screen_donor(donor_data)
                risk_result = risk_score(donor_data)
            except EngineError as exc:
                alert_banner(f"Check the entries: {exc}", "danger")
            else:
                ok, save_error, _ = attempt(record_screening, user, donor["id"], sel_hosp_id, hiv=hiv, hepatitis_b=hep_b,
                                            hepatitis_c=hep_c, syphilis=syphilis, malaria=malaria,
                                            decision=screen_result["decision"], risk_score=int(risk_result["score"]))
                if not ok:
                    alert_banner(save_error or "Could not save the screening.", "danger")

                decision = screen_result["decision"]
                level = {"SAFE": "success", "DEFER": "warning", "BLOCK": "danger"}[decision]
                st.markdown(f"""
                <div class='glass-hero' style='margin-top:16px;'>
                    <h3 style='margin:0 0 10px;font-family:"Syne",sans-serif;'>Screening Outcome</h3>
                    <div style='display:flex;align-items:center;gap:12px;margin-bottom:12px;'>
                        {status_pill(decision)}
                        <span style='font-size:0.9rem;color:var(--text-secondary);'>Risk Score: <strong>{risk_result['score']}/100</strong></span>
                    </div>
                </div>""", unsafe_allow_html=True)
                alert_banner(risk_result["recommendation"], level)

                if screen_result["fired_rules"]:
                    section_header("Why", "Every rule that fired")
                    styled_table(pd.DataFrame([{"Rule": r["rule_name"].replace("_", " "), "Outcome": status_pill(r["decision"]),
                                                "Reason": r["reason"]} for r in screen_result["fired_rules"]]))
                with st.expander("Full inference trace"):
                    for line in screen_result["inference_chain"]:
                        st.markdown(f"• {line}")
