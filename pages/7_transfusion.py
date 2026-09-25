# pages/7_transfusion.py
"""Transfusion Monitoring — LIFELINE v6.0"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Transfusion — LIFELINE", layout="wide")

from utils.styles import (
    inject_all_styles, get_theme, section_header, alert_banner,
    blood_badge, status_pill, styled_table, metric_card,
)
from lifeline.auth.roles import Role
from utils.sidebar import render_sidebar
from utils.database import (
    get_all_hospitals, get_transfusions, add_transfusion,
    get_donors, add_audit_log, update_blood_units,
)
from dsa_engine import BLOOD_GROUPS, get_compatible_donors

if not st.session_state.get("logged_in"):
    st.switch_page("app.py")
    st.stop()

inject_all_styles(get_theme())
render_sidebar()

_role = st.session_state.get("user_role", "")
_hosp_id = st.session_state.get("user_hospital_id")
_uid = int(st.session_state.get("user_id", 0))
_hosp_name = st.session_state.get("user_hospital_name", "")

# ── Title Block ──
st.markdown("""
<div style="margin-bottom:24px">
    <h1 style="font-family:'Syne',sans-serif;font-size:1.6rem;margin:0">Transfusion Management</h1>
    <p style="color:var(--text-secondary);font-size:0.82rem;margin:4px 0 0">
        Record transfusions and monitor patient reactions
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

tab1, tab2, tab3 = st.tabs(["Transfusion Log", "Record Transfusion", "Reaction Monitor"])

with tab1:
    transfusions = get_transfusions(sel_hosp_id)
    if not transfusions:
        alert_banner("No transfusion records yet.", "info")
    else:
        total_u = sum(t.get("units", 0) for t in transfusions)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(metric_card("Total Transfusions", f"{len(transfusions)}", icon="Transfusion", variant="default"), unsafe_allow_html=True)
        with c2:
            st.markdown(metric_card("Units Transfused", f"{total_u}", icon="Units", variant="success"), unsafe_allow_html=True)

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        log_rows = []
        for t in transfusions:
            log_rows.append({
                "Patient": t.get("patient_name", "—"),
                "Blood Group": blood_badge(t.get("blood_group", "?")),
                "Units": f"{t.get('units', 0)}u",
                "Date/Time": t.get("transfused_at", "")[:16].replace("T", " "),
                "Performed By": t.get("performed_by", "—"),
                "Notes": t.get("notes", "—")
            })
        df_show = pd.DataFrame(log_rows)
        styled_table(df_show)

with tab2:
    section_header("Record New Transfusion")

    # Compatibility check helper
    check_bg = st.selectbox("Patient Blood Group (for compatibility check)", BLOOD_GROUPS, key="compat_bg")
    compatible = get_compatible_donors(check_bg)
    
    # We construct a compatibility description using blood_badge for styling
    compat_badges_html = " ".join([blood_badge(c) for c in compatible])
    st.markdown(f"""
    <div style='margin-bottom:16px;'>
        <div style='font-size:0.85rem;color:var(--text-secondary);margin-bottom:6px;'>Compatible Donor Groups:</div>
        <div>{compat_badges_html}</div>
    </div>""", unsafe_allow_html=True)

    error_msg = None
    success_msg = None

    with st.form("transfusion_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            patient_name = st.text_input("Patient Name *")
        with col2:
            blood_grp = st.selectbox("Blood Group Used", BLOOD_GROUPS, key="t_bg",
                                     index=BLOOD_GROUPS.index(check_bg))
        with col3:
            units = st.number_input("Units Transfused", min_value=1, max_value=20, value=1)

        performed_by = st.text_input("Performed By (Physician / Nurse)")
        notes = st.text_area("Clinical Notes", placeholder="Indications, observations, reaction notes...")

        submitted = st.form_submit_button("Record Transfusion", use_container_width=True)
        if submitted:
            if not patient_name:
                error_msg = "Patient name is required."
            elif blood_grp not in compatible:
                error_msg = f"Incompatibility Warning: {blood_grp} is NOT compatible with patient blood group {check_bg}!"
            else:
                ok = add_transfusion(sel_hosp_id, patient_name, blood_grp, units, performed_by, notes)
                if ok:
                    update_blood_units(sel_hosp_id, blood_grp, -units, f"Transfusion: {patient_name}", _uid)
                    add_audit_log("TRANSFUSION", f"Transfused {units}u {blood_grp} to {patient_name} at {sel_name}", _uid)
                    success_msg = f"Transfusion recorded for {patient_name}"

        if success_msg:
            alert_banner(success_msg, "success")
            st.rerun()
        elif error_msg:
            alert_banner(error_msg, "danger")

with tab3:
    section_header("Transfusion Reaction Monitor", "Model-Based Reflex Agent")
    st.caption("Enter pre and post-transfusion vitals to detect adverse reactions")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Pre-Transfusion Vitals:**")
        pre_temp = st.number_input("Temperature (°C)", 35.0, 42.0, 36.8, key="pre_temp")
        pre_bp = st.number_input("BP Systolic (mmHg)", 60, 200, 120, key="pre_bp")
        pre_pulse = st.number_input("Pulse (bpm)", 40, 180, 75, key="pre_pulse")
        pre_o2 = st.number_input("O₂ Saturation (%)", 70.0, 100.0, 99.0, key="pre_o2")

    with col2:
        st.markdown("**Post-Transfusion Vitals:**")
        post_temp = st.number_input("Temperature (°C)", 35.0, 42.0, 37.0, key="post_temp")
        post_bp = st.number_input("BP Systolic (mmHg)", 60, 200, 118, key="post_bp")
        post_pulse = st.number_input("Pulse (bpm)", 40, 180, 78, key="post_pulse")
        post_o2 = st.number_input("O₂ Saturation (%)", 70.0, 100.0, 98.0, key="post_o2")

    if st.button("Analyse Reaction", use_container_width=True):
        from utils.dsa_engine import transfusion_monitor
        pre = {"temp": pre_temp, "bp_systolic": pre_bp, "pulse": pre_pulse, "o2_sat": pre_o2}
        post = {"temp": post_temp, "bp_systolic": post_bp, "pulse": post_pulse, "o2_sat": post_o2}
        result = transfusion_monitor({"pre": pre, "post": post})

        reaction = result["reaction_type"]
        severity = result["severity"]
        action = result["action"]
        alert_color = result.get("alert_color", "green")

        dec_level = {"red": "danger", "amber": "warning", "green": "success"}.get(alert_color, "info")

        st.markdown(f"""
        <div class='glass-hero' style='margin-top:16px;'>
            <h3 style='margin:0 0 10px;font-family:"Syne",sans-serif;'>Reflex Agent Analysis</h3>
            <div style='display:flex;align-items:center;gap:12px;margin-bottom:12px;'>
                {status_pill(reaction)}
                <span style='font-size:0.9rem;color:var(--text-secondary);'>Severity: <strong>{severity}</strong></span>
            </div>
        </div>""", unsafe_allow_html=True)
        
        # Action Banner
        alert_banner(action, dec_level)
        
        st.markdown(f"""
        <div style='margin-top:12px;font-size:0.82rem;color:var(--text-secondary);font-family:"JetBrains Mono",monospace;'>
        ΔTemp: {result["deltas"]["temp_rise"]:+.1f}°C &nbsp;|&nbsp;
        ΔBP: {result["deltas"]["bp_drop"]:+.0f} mmHg &nbsp;|&nbsp;
        ΔO₂: {result["deltas"]["o2_change"]:+.1f}%
        </div>""", unsafe_allow_html=True)

