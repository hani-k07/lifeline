import streamlit as st
import pandas as pd
from datetime import datetime
import time

from utils.supabase_client import (
    get_patients, get_blood_units, get_transfusion_records,
    add_transfusion_record, add_audit_log
)
from utils.dsa_bridge import detect_reaction

if not st.session_state.get("logged_in"):
    st.warning("Please login from the main page.")
    st.stop()

from utils.sidebar import render_sidebar
render_sidebar()


role    = st.session_state.get("user_role")
hosp_id = st.session_state.get("hospital_id") if role != "super_admin" else None

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'Outfit',sans-serif!important;}
.stApp{background:linear-gradient(-45deg,#0f0c29,#302b63,#24243e,#1a1a2e);background-size:400% 400%;animation:gradientBG 15s ease infinite;}
@keyframes gradientBG{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
footer,#MainMenu{visibility:hidden;} [data-testid='stSidebarNav'] { display: none !important; } [data-testid='stHeader'] { background: transparent !important; } [data-testid='stHeaderActionElements'] { display: none !important; }
.block-container{padding-top:1.5rem!important;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0D0D1A 0%,#1C1C2E 100%)!important;border-right:1px solid rgba(255,65,108,0.2);}
[data-testid="stSidebar"] *{color:#ECF0F1!important;}
.glass-card{background:rgba(20,20,35,0.7);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:24px;margin-bottom:16px;box-shadow:0 8px 32px rgba(0,0,0,0.4);transition:all 0.3s ease;}
.section-header{font-size:0.68rem;font-weight:600;color:#ff416c;text-transform:uppercase;letter-spacing:2px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid rgba(255,65,108,0.2);}
.vital-box{background:rgba(0,0,0,0.4);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:15px;text-align:center;}
.vital-val{font-size:2rem;font-weight:700;color:white;}
.vital-lbl{font-size:0.7rem;color:#95A5A6;text-transform:uppercase;}
.stTextInput>div>div>input,.stSelectbox>div>div>div,.stNumberInput>div>div>input{background:rgba(0,0,0,0.3)!important;border:1px solid rgba(255,255,255,0.1)!important;color:white!important;border-radius:10px!important;}
.stButton>button{background:linear-gradient(135deg,#ff416c,#ff4b2b)!important;color:white!important;border:none!important;border-radius:10px!important;font-weight:600!important;box-shadow:0 4px 15px rgba(255,65,108,0.3)!important;}
</style>""", unsafe_allow_html=True)

st.markdown("<h1 style='color:white;'><span style='color:#E74C3C;'>💉</span> Vitals Telemetry & Transfusion Monitor</h1>", unsafe_allow_html=True)

# ── SETUP MONITORING ────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>START TELEMETRY SESSION</div>", unsafe_allow_html=True)

patients = get_patients(hosp_id)
units    = get_blood_units(hosp_id)

if not patients or not units:
    st.warning("Need both patients and available units in your hospital to monitor a transfusion.")
    st.stop()

p_opts = {f"{p['full_name']} ({p['blood_group']})": p["id"] for p in patients}
u_opts = {f"{u['unit_code']} ({u['blood_group']})": u["id"] for u in units}

with st.form("transfusion_form"):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<h4 style='color:white;'>1. Session Setup</h4>", unsafe_allow_html=True)
        p_sel = st.selectbox("Select Patient", list(p_opts.keys()))
        u_sel = st.selectbox("Select Blood Unit", list(u_opts.keys()))
        nurse = st.text_input("Attending Nurse Name")
        
        st.markdown("<h4 style='color:white;margin-top:20px;'>2. T=0 (Baseline Pre-Vitals)</h4>", unsafe_allow_html=True)
        pre_sys = st.number_input("Pre BP Systolic", value=120)
        pre_dia = st.number_input("Pre BP Diastolic", value=80)
        pre_pul = st.number_input("Pre Pulse (bpm)", value=72)
        pre_tem = st.number_input("Pre Temp (°C)", value=37.0, step=0.1)
        pre_o2  = st.number_input("Pre O2 Sat (%)", value=98)
        
    with c2:
        st.markdown("<h4 style='color:white;margin-top:103px;'>3. T+15 (Post-Vitals)</h4>", unsafe_allow_html=True)
        post_sys = st.number_input("Post BP Systolic", value=120)
        post_dia = st.number_input("Post BP Diastolic", value=80)
        post_pul = st.number_input("Post Pulse (bpm)", value=72)
        post_tem = st.number_input("Post Temp (°C)", value=37.0, step=0.1)
        post_o2  = st.number_input("Post O2 Sat (%)", value=98)
        
    st.markdown("<br>", unsafe_allow_html=True)
    submitted = st.form_submit_button("ACTIVATE AI REFLEX AGENT 🤖", use_container_width=True)

if submitted:
    pre_vitals  = {"bp_sys": pre_sys, "bp_dia": pre_dia, "pulse": pre_pul, "temp": pre_tem, "o2": pre_o2}
    post_vitals = {"bp_sys": post_sys, "bp_dia": post_dia, "pulse": post_pul, "temp": post_tem, "o2": post_o2}
    
    with st.spinner("AI ANALYZING TELEMETRY DELTAS..."):
        reaction = detect_reaction(pre_vitals, post_vitals)
        time.sleep(1)
        
        rxn  = reaction.get("reaction", "NORMAL")
        act  = reaction.get("action", "")
        rule = reaction.get("rule", "")
        
        # Save to DB
        record = {
            "patient_id": p_opts[p_sel], "unit_id": u_opts[u_sel], "hospital_id": hosp_id,
            "pre_bp_sys": pre_sys, "pre_bp_dia": pre_dia, "pre_pulse": pre_pul, "pre_temp": pre_tem, "pre_o2": pre_o2,
            "post_bp_sys": post_sys, "post_bp_dia": post_dia, "post_pulse": post_pul, "post_temp": post_tem, "post_o2": post_o2,
            "reaction_type": rxn, "action_taken": act, "nurse_name": nurse
        }
        add_transfusion_record(record)
        add_audit_log("TRANSFUSION_LOGGED", st.session_state["email"], hosp_id, "transfusion", p_opts[p_sel], {"reaction": rxn})
        
        # Display Result
        if rxn == "NORMAL":
            st.markdown(f"""<div class='glass-card' style='border-color:#00D2AA;text-align:center;'>
                <h2 style='color:#00D2AA;margin:0;'>STATUS: NOMINAL</h2>
                <p style='color:white;font-size:1.2rem;'>{act}</p>
            </div>""", unsafe_allow_html=True)
        elif rxn == "FEVER":
            st.markdown(f"""<div class='glass-card' style='border-color:#FFB347;text-align:center;'>
                <h2 style='color:#FFB347;margin:0;'>WARNING: FEBRILE REACTION</h2>
                <p style='color:white;font-size:1.2rem;'>{act}</p>
                <code style='color:#FFB347;'>Trigger: {rule}</code>
            </div>""", unsafe_allow_html=True)
        elif rxn == "HEMOLYTIC":
            st.markdown(f"""<div class='glass-card' style='border-color:#E74C3C;text-align:center;'>
                <h2 style='color:#E74C3C;margin:0;'>CRITICAL: HEMOLYTIC REACTION</h2>
                <p style='color:white;font-size:1.5rem;font-weight:700;'>{act}</p>
                <code style='color:#E74C3C;'>Trigger: {rule}</code>
            </div>""", unsafe_allow_html=True)
        else: # ANAPHYLAXIS
            st.markdown(f"""<div class='glass-card' style='border-color:#E74C3C;text-align:center;animation:pulse-red 1s infinite;'>
                <h1 style='color:#ff416c;margin:0;'>🚨 ANAPHYLAXIS DETECTED 🚨</h1>
                <p style='color:white;font-size:2rem;font-weight:800;'>{act}</p>
                <code style='color:#ff416c;font-size:1.1rem;'>Trigger: {rule}</code>
            </div>""", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# ── VITALS STACK ────────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>LATEST TRANSFUSIONS (LIFO STACK)</div>", unsafe_allow_html=True)

records = get_transfusion_records(hosp_id)
if records:
    st.markdown("<p style='color:#95A5A6;font-size:0.8rem;'>DSA: Stack (LIFO) ensures the most recent telemetry readings are always accessed first in O(1) time.</p>", unsafe_allow_html=True)
    
    for i, r in enumerate(records[:3]):
        rxn = r.get("reaction_type","NORMAL")
        col = "#00D2AA" if rxn=="NORMAL" else ("#FFB347" if rxn=="FEVER" else "#E74C3C")
        
        st.markdown(f"""<div style='background:rgba(0,0,0,0.4);border:1px solid {col};border-radius:12px;padding:15px;margin-bottom:10px;'>
            <div style='display:flex;justify-content:space-between;margin-bottom:10px;'>
                <b style='color:white;'>Patient: {r.get('patient_name')}</b>
                <span style='color:{col};font-weight:bold;'>{rxn}</span>
            </div>
            <div style='display:flex;gap:10px;'>
                <div class='vital-box' style='flex:1;'><div class='vital-lbl'>BP Sys</div><div class='vital-val'>{r.get('post_bp_sys')}</div><div style='font-size:0.6rem;color:#95A5A6;'>Pre: {r.get('pre_bp_sys')}</div></div>
                <div class='vital-box' style='flex:1;'><div class='vital-lbl'>BP Dia</div><div class='vital-val'>{r.get('post_bp_dia')}</div><div style='font-size:0.6rem;color:#95A5A6;'>Pre: {r.get('pre_bp_dia')}</div></div>
                <div class='vital-box' style='flex:1;'><div class='vital-lbl'>Pulse</div><div class='vital-val'>{r.get('post_pulse')}</div><div style='font-size:0.6rem;color:#95A5A6;'>Pre: {r.get('pre_pulse')}</div></div>
                <div class='vital-box' style='flex:1;'><div class='vital-lbl'>Temp</div><div class='vital-val'>{r.get('post_temp')}°</div><div style='font-size:0.6rem;color:#95A5A6;'>Pre: {r.get('pre_temp')}°</div></div>
                <div class='vital-box' style='flex:1;'><div class='vital-lbl'>O2 Sat</div><div class='vital-val'>{r.get('post_o2')}%</div><div style='font-size:0.6rem;color:#95A5A6;'>Pre: {r.get('pre_o2')}%</div></div>
            </div>
        </div>""", unsafe_allow_html=True)
else:
    st.info("No transfusion records.")
st.markdown("</div>", unsafe_allow_html=True)
