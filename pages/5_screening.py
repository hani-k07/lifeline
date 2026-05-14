import streamlit as st
import sqlite3
import uuid
import json
from datetime import datetime

try:
    from utils.styles import get_glass_css
except ImportError:
    def get_glass_css(): return ""
    
from utils.cpp_bridge import run_dsa_engine
from utils.ai_engine import DonorScreeningEngine, RuleBasedStrategy
from utils.repository import DatabaseManager

# Role Check
if st.session_state.get("user_role") not in ["staff", "hospital_admin", "super_admin"]:
    st.error("Access Denied")
    st.stop()

st.markdown(get_glass_css(), unsafe_allow_html=True)
st.title("Donor AI Screening")

st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<h2 class='section-header'>Donor Input Form</h2>", unsafe_allow_html=True)

with st.form("donor_screening_form"):
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Full Name", key="donor_name")
        st.number_input("Age", min_value=18, max_value=65, value=25, key="donor_age")
        st.number_input("Systolic BP", value=120, key="donor_sys")
        st.number_input("Days since last donation", min_value=0, max_value=3650, value=120, key="donor_days")
        st.number_input("Hemoglobin (g/dL)", min_value=5.0, max_value=20.0, step=0.1, value=14.0, key="donor_hemo")
        st.number_input("Temperature (°C)", min_value=35.0, max_value=42.0, step=0.1, value=37.0, key="donor_temp")
    
    with col2:
        st.text_input("CNIC", key="donor_cnic")
        st.number_input("Weight (kg)", min_value=40.0, max_value=120.0, value=70.0, key="donor_weight")
        st.number_input("Diastolic BP", value=80, key="donor_dia")
        st.number_input("Pulse (bpm)", min_value=40, max_value=160, value=75, key="donor_pulse")
        st.checkbox("On Blood Thinners", key="donor_thinners")
        st.multiselect("Diseases", ["Diabetes", "Hypertension", "HepB", "HepC", "HIV", "Malaria", "Syphilis", "None"], key="donor_diseases")

    st.markdown("### Rapid Screening Results")
    col3, col4, col5 = st.columns(3)
    with col3:
        st.selectbox("HIV", ["negative", "positive"], key="screen_hiv")
        st.selectbox("HepB", ["negative", "positive"], key="screen_hepb")
    with col4:
        st.selectbox("HepC", ["negative", "positive"], key="screen_hepc")
        st.selectbox("Syphilis", ["negative", "positive"], key="screen_syphilis")
    with col5:
        st.selectbox("Malaria", ["negative", "positive"], key="screen_malaria")

    submitted = st.form_submit_button("RUN AI SCREENING")

st.markdown("</div>", unsafe_allow_html=True)

if submitted:
    diseases_clean = [d for d in st.session_state.donor_diseases if d != "None"]
    
    donor_payload = {
        "donor": {
            "age": st.session_state.donor_age,
            "weight_kg": st.session_state.donor_weight,
            "on_blood_thinners": st.session_state.donor_thinners,
            "days_since_last_donation": st.session_state.donor_days,
            "diseases": diseases_clean,
            "systolic_bp": st.session_state.donor_sys,
            "diastolic_bp": st.session_state.donor_dia
        }
    }
    
    vitals_payload = {
        "vitals": {
            "hiv_status": st.session_state.screen_hiv,
            "hepb_status": st.session_state.screen_hepb,
            "hepc_status": st.session_state.screen_hepc,
            "syphilis_status": st.session_state.screen_syphilis,
            "malaria_status": st.session_state.screen_malaria,
            "hemoglobin": st.session_state.donor_hemo,
            "pulse": st.session_state.donor_pulse,
            "temp_c": st.session_state.donor_temp
        }
    }
    
    # Python AI Fallback Analysis
    python_engine = DonorScreeningEngine(RuleBasedStrategy())
    python_payload = {
        "age": st.session_state.donor_age,
        "weight": st.session_state.donor_weight,
        "on_blood_thinners": st.session_state.donor_thinners,
        "days_since_last_donation": st.session_state.donor_days,
        "diseases": diseases_clean,
        "systolic_bp": st.session_state.donor_sys,
        "diastolic_bp": st.session_state.donor_dia
    }
    
    python_res = None
    c_risk_res = None
    c_expert_res = None
    
    try:
        python_res = python_engine.evaluate_donor(python_payload)
    except Exception as e:
        st.warning(f"Python AI Engine Failed: {e}")
        
    try:
        c_risk_res = run_dsa_engine("risk_score", donor_payload)
        if c_risk_res and c_risk_res.get("fallback"):
            st.warning(f"C++ Engine Risk Score Fallback: {c_risk_res}")
    except Exception as e:
        st.warning(f"C++ Engine Call Failed: {e}")

    try:
        c_expert_res = run_dsa_engine("expert_screen", vitals_payload)
        if c_expert_res and c_expert_res.get("fallback"):
            st.warning(f"C++ Engine Expert Screen Fallback: {c_expert_res}")
    except Exception as e:
        st.warning(f"C++ Engine Call Failed: {e}")
        
    st.session_state["screening_results"] = {
        "python_res": python_res,
        "c_risk_res": c_risk_res,
        "c_expert_res": c_expert_res
    }

if st.session_state.get("screening_results"):
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<h2 class='section-header'>Screening Results</h2>", unsafe_allow_html=True)
    
    res = st.session_state["screening_results"]
    c_risk_res = res.get("c_risk_res")
    c_expert_res = res.get("c_expert_res")
    python_res = res.get("python_res")
    
    # Python AI Engine Display block
    if python_res:
        st.markdown("### Python Expert System (Fallback Verification)")
        st.markdown(f"**Score:** {python_res.get('final_score')} | **Classification:** {python_res.get('classification')}")
    
    if c_risk_res and not c_risk_res.get("fallback"):
        st.markdown("### C++ Heuristics Engine")
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.metric("Final Score", c_risk_res.get("final_score", 0))
            
        cls_val = c_risk_res.get("classification", "BLOCKED")
        badge_class = "badge-critical" if cls_val == "BLOCKED" else ("badge-caution" if cls_val == "CAUTION" else "badge-info")
        
        with col_res2:
            st.markdown(f"<span class='badge {badge_class}'>{cls_val}</span>", unsafe_allow_html=True)
            
        if cls_val == "BLOCKED":
            st.error("**DONOR INELIGIBLE — DO NOT PROCEED**")
        elif cls_val == "CAUTION":
            st.warning("Proceed with caution. Additional review recommended.")
        else:
            st.success("Donor is healthy and eligible for donation.")
            
        penalties = c_risk_res.get("penalties", [])
        if penalties:
            st.markdown("#### Deduction Penalties")
            table_html = "<table class='data-table'><tr><th>Rule</th><th>Deduction</th><th>Reason</th></tr>"
            for p in penalties:
                table_html += f"<tr><td>{p.get('rule')}</td><td>{p.get('deduction')}</td><td>{p.get('reason')}</td></tr>"
            table_html += "</table>"
            st.markdown(table_html, unsafe_allow_html=True)
            
    if c_expert_res and not c_expert_res.get("fallback"):
        st.markdown("### Expert System Diagnostics")
        st.markdown(f"**Verdict:** {c_expert_res.get('verdict')}")
        chain = c_expert_res.get('inference_chain', [])
        if chain:
            st.markdown(f"**Inference Chain:** {' &rarr; '.join(chain)}", unsafe_allow_html=True)
        
        fired = c_expert_res.get("fired_rules", [])
        if fired:
            table_html = "<table class='data-table'><tr><th>Rule</th><th>Consequence</th><th>Action</th><th>Priority</th></tr>"
            for r in fired:
                table_html += f"<tr><td>{r.get('rule')}</td><td>{r.get('consequence')}</td><td>{r.get('action')}</td><td>{r.get('priority')}</td></tr>"
            table_html += "</table>"
            st.markdown(table_html, unsafe_allow_html=True)
            
    if c_risk_res and c_risk_res.get("classification") != "BLOCKED":
        if st.button("Save to Database"):
            try:
                with DatabaseManager() as db:
                    donor_id = str(uuid.uuid4())
                    db.execute_write(
                        "INSERT INTO donors (id, full_name, cnic, age, weight_kg, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (donor_id, st.session_state.donor_name, st.session_state.donor_cnic, st.session_state.donor_age, st.session_state.donor_weight, datetime.utcnow().isoformat())
                    )
                st.success("Donor saved to database successfully.")
                del st.session_state["screening_results"]
            except Exception as e:
                st.error(f"Database error: {e}")

    st.markdown("</div>", unsafe_allow_html=True)
