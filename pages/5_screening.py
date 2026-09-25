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
from lifeline.auth.roles import Role
from utils.sidebar import render_sidebar
from utils.database import (
    get_all_hospitals, get_donors, add_donor,
    get_screening_tests, add_screening_test, add_audit_log,
)
from dsa_engine import BLOOD_GROUPS

require_page(__file__)

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
                "CNIC": d.get("cnic", "—"),
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
    success_msg = None
    
    with st.form("donor_form"):
        col1, col2 = st.columns(2)
        with col1:
            d_name = st.text_input("Full Name *")
            d_cnic = st.text_input("CNIC", placeholder="35202-XXXXXXX-X")
            d_phone = st.text_input("Phone", placeholder="0300-XXXXXXX")
        with col2:
            d_bg = st.selectbox("Blood Group *", BLOOD_GROUPS)
            d_last = st.date_input("Last Donation Date (if any)", value=None)
            d_notes = st.text_area("Medical Notes", placeholder="Any conditions, medications...")

        submitted = st.form_submit_button("Register Donor", use_container_width=True)
        if submitted:
            if not d_name:
                error_msg = "Donor name is required."
            else:
                ok = add_donor(
                    name=d_name, cnic=d_cnic, phone=d_phone,
                    blood_group=d_bg, hospital_id=sel_hosp_id,
                    last_donated=str(d_last) if d_last else None,
                    notes=d_notes
                )
                if ok:
                    add_audit_log("DONOR_REGISTERED", f"New donor {d_name} ({d_bg}) registered at {sel_name}", _uid)
                    success_msg = f"Donor {d_name} registered successfully!"
                else:
                    error_msg = "Failed to register donor."

    if success_msg:
        alert_banner(success_msg, "success")
        st.rerun()
    elif error_msg:
        alert_banner(error_msg, "danger")

with tab3:
    section_header("Blood Screening Test", "Forward-Chain Expert System & Hill-Climbing Risk Scorer")

    donors = get_donors(sel_hosp_id)
    if not donors:
        alert_banner("No donors registered. Register a donor first.", "warning")
    else:
        donor_map = {f"{d['name']} ({d['blood_group']})": d["id"] for d in donors}
        sel_donor_label = st.selectbox("Select Donor", list(donor_map.keys()))
        sel_donor_id = donor_map[sel_donor_label]

        st.markdown("**Serology Panel:**")
        cols = st.columns(5)
        hiv = cols[0].checkbox("HIV")
        hep_b = cols[1].checkbox("Hepatitis B")
        hep_c = cols[2].checkbox("Hepatitis C")
        syphilis = cols[3].checkbox("Syphilis")
        malaria = cols[4].checkbox("Malaria")

        st.markdown("**Donor Vitals:**")
        vcol1, vcol2, vcol3, vcol4 = st.columns(4)
        age = vcol1.number_input("Age", 18, 65, 30)
        weight = vcol2.number_input("Weight (kg)", 40.0, 120.0, 65.0)
        hemoglobin = vcol3.number_input("Hemoglobin (g/dL)", 8.0, 20.0, 14.0)
        bp_sys = vcol4.number_input("BP Systolic", 80, 200, 120)

        if st.button("Run Screening", use_container_width=True):
            # Expert system via dsa_engine
            from dsa_engine import screen_donor, risk_score
            donor_data = {
                "age": age, "weight": weight, "hemoglobin": hemoglobin,
                "bp_systolic": bp_sys, "hiv": hiv, "hepb": hep_b,
                "hepc": hep_c, "syphilis": syphilis, "malaria": malaria,
                "diseases": [],
            }
            screen_result = screen_donor({"donor": donor_data})
            risk_result = risk_score({"donor": {**donor_data, "last_donation_days": 365}})

            ok = add_screening_test(sel_donor_id, sel_hosp_id, hiv, hep_b, hep_c, syphilis, malaria)
            add_audit_log("SCREENING", f"Screening for donor ID {sel_donor_id}: {screen_result['decision']}", _uid)

            decision = screen_result["decision"]
            dec_level = {"SAFE": "success", "DEFER": "warning", "BLOCK": "danger"}.get(decision, "info")

            st.markdown(f"""
            <div class='glass-hero' style='margin-top:16px;'>
                <h3 style='margin:0 0 10px;font-family:"Syne",sans-serif;'>Screening Outcome</h3>
                <div style='display:flex;align-items:center;gap:12px;margin-bottom:12px;'>
                    {status_pill(decision)}
                    <span style='font-size:0.9rem;color:var(--text-secondary);'>Risk Score: <strong>{risk_result['score']}/100</strong></span>
                </div>
            </div>""", unsafe_allow_html=True)
            
            # Recommendation Banner
            alert_banner(risk_result['recommendation'], dec_level)

            if screen_result["fired_rules"]:
                with st.expander("Expert System Inference Chain"):
                    for rule in screen_result["fired_rules"]:
                        st.markdown(f"• **{rule['rule_name']}** (priority {rule['priority']}): {rule['reason']}")

