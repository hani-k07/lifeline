import streamlit as st
import sqlite3
import uuid
import json
from datetime import datetime

try:
    from utils.styles import get_glass_css
except ImportError:
    def get_glass_css(): return ""

from utils.ai_engine import TransfusionMonitorAgent
from utils.repository import DatabaseManager

if st.session_state.get("user_role") not in ["staff", "hospital_admin", "super_admin"]:
    st.error("Access Denied")
    st.stop()

hospital_id = st.session_state.get("hospital_id", "UNKNOWN")

st.markdown(get_glass_css(), unsafe_allow_html=True)
st.title("Live Transfusion Monitor")

st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<h2 class='section-header'>Patient & Unit Selection</h2>", unsafe_allow_html=True)

patients = []
try:
    with DatabaseManager() as db:
        patients = db.execute("SELECT id, name FROM patients WHERE hospital_id = ?", (hospital_id,))
except Exception as e:
    st.warning("Could not load patients from DB. Proceeding with manual entry mode.")

patient_options = {p['id']: p['name'] for p in patients} if patients else {}

col_sel1, col_sel2 = st.columns(2)
with col_sel1:
    selected_patient_id = st.selectbox("Select Patient", options=list(patient_options.keys()), format_func=lambda x: patient_options.get(x, x), key="trans_patient")
with col_sel2:
    blood_unit_id = st.text_input("Blood Unit ID", key="trans_unit")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<h2 class='section-header'>Vitals Entry</h2>", unsafe_allow_html=True)

col_pre, col_post = st.columns(2)
with col_pre:
    st.markdown("### Pre-Transfusion")
    st.number_input("Pre BP Systolic", min_value=50, max_value=250, value=120, key="pre_sys")
    st.number_input("Pre BP Diastolic", min_value=30, max_value=150, value=80, key="pre_dia")
    st.number_input("Pre Pulse", min_value=30, max_value=200, value=75, key="pre_pulse")
    st.number_input("Pre Temp (°C)", min_value=30.0, max_value=45.0, value=37.0, step=0.1, key="pre_temp")
    st.number_input("Pre O2 Sat (%)", min_value=50, max_value=100, value=98, key="pre_o2")

with col_post:
    st.markdown("### Post-Transfusion")
    st.number_input("Post BP Systolic", min_value=50, max_value=250, value=120, key="post_sys")
    st.number_input("Post BP Diastolic", min_value=30, max_value=150, value=80, key="post_dia")
    st.number_input("Post Pulse", min_value=30, max_value=200, value=75, key="post_pulse")
    st.number_input("Post Temp (°C)", min_value=30.0, max_value=45.0, value=37.0, step=0.1, key="post_temp")
    st.number_input("Post O2 Sat (%)", min_value=50, max_value=100, value=98, key="post_o2")

analyze_btn = st.button("ANALYZE VITALS")
st.markdown("</div>", unsafe_allow_html=True)

if analyze_btn:
    pre_dict = {
        "bp_sys": st.session_state.pre_sys, "bp_dia": st.session_state.pre_dia, 
        "pulse": st.session_state.pre_pulse, "temp_c": st.session_state.pre_temp, "o2_sat": st.session_state.pre_o2
    }
    post_dict = {
        "bp_sys": st.session_state.post_sys, "bp_dia": st.session_state.post_dia, 
        "pulse": st.session_state.post_pulse, "temp_c": st.session_state.post_temp, "o2_sat": st.session_state.post_o2
    }
    
    agent = TransfusionMonitorAgent()
    try:
        report = agent.analyze(pre_dict, post_dict)
        st.session_state["transfusion_report"] = report
    except Exception as e:
        st.warning(f"AI Engine Failed: {e}")
        st.session_state.pop("transfusion_report", None)

if st.session_state.get("transfusion_report"):
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<h2 class='section-header'>Analysis Report</h2>", unsafe_allow_html=True)
    
    report = st.session_state["transfusion_report"]
    reaction = report.get("reaction", "UNKNOWN")
    severity = report.get("severity", "NORMAL")
    action = report.get("action", "")
    deltas = report.get("deltas", {})
    
    if severity == "CRITICAL":
        st.error(f"🚨 **{reaction} DETECTED! STOP TRANSFUSION IMMEDIATELY** 🚨")
    elif severity == "WARNING":
        st.warning(f"⚠️ **{reaction} DETECTED!**")
    else:
        st.success(f"✅ **{reaction} - Vitals Stable**")
        
    st.markdown(f"**Action Required:** {action}")
    
    st.markdown("### Vitals Delta")
    table_html = "<table class='data-table'><tr><th>Metric</th><th>Pre</th><th>Post</th><th>Delta</th></tr>"
    table_html += f"<tr><td>BP Sys</td><td>{st.session_state.pre_sys}</td><td>{st.session_state.post_sys}</td><td>{deltas.get('bp_drop', 0) * -1:.2f}</td></tr>"
    table_html += f"<tr><td>Pulse</td><td>{st.session_state.pre_pulse}</td><td>{st.session_state.post_pulse}</td><td>{deltas.get('pulse_rise', 0):.2f}</td></tr>"
    table_html += f"<tr><td>Temp</td><td>{st.session_state.pre_temp}</td><td>{st.session_state.post_temp}</td><td>{deltas.get('temp_rise', 0):.2f}</td></tr>"
    table_html += f"<tr><td>O2 Sat</td><td>{st.session_state.pre_o2}</td><td>{st.session_state.post_o2}</td><td>{deltas.get('o2_drop', 0) * -1:.2f}</td></tr>"
    table_html += "</table>"
    st.markdown(table_html, unsafe_allow_html=True)
    
    if st.button("LOG REACTION TO DATABASE"):
        try:
            with DatabaseManager() as db:
                record_id = str(uuid.uuid4())
                patient_id_val = st.session_state.trans_patient if st.session_state.trans_patient else "UNKNOWN"
                unit_id_val = st.session_state.trans_unit if st.session_state.trans_unit else "UNKNOWN"
                
                db.execute_write(
                    "INSERT INTO transfusion_records (id, hospital_id, patient_id, blood_unit_id, reaction_type, severity, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (record_id, hospital_id, patient_id_val, unit_id_val, reaction, severity, json.dumps(deltas), datetime.utcnow().isoformat())
                )
            st.success("Transfusion record logged securely.")
            del st.session_state["transfusion_report"]
        except Exception as e:
            st.error(f"Database error: {e}")

    st.markdown("</div>", unsafe_allow_html=True)
