import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

from utils.supabase_client import (
    add_donor, get_donors, get_patients, get_blood_units, add_audit_log
)
from utils.dsa_bridge import calculate_risk_score, screen_donor

if not st.session_state.get("logged_in"):
    st.warning("Please login from the main page.")
    st.stop()

from utils.sidebar import render_sidebar
render_sidebar()


role    = st.session_state.get("user_role")
hosp_id = st.session_state.get("hospital_id") if role != "super_admin" else None

from utils.styles import get_glass_css
st.markdown(get_glass_css(), unsafe_allow_html=True)

st.markdown("<h1 style='color:white;'><span style='color:#00D2AA;'>🔬</span> Medical Screening Laboratory</h1>", unsafe_allow_html=True)

donors = get_donors()
safe    = sum(1 for d in donors if d.get("risk_score",0) >= 80)
caution = sum(1 for d in donors if 50 <= d.get("risk_score",0) < 80)
blocked = sum(1 for d in donors if d.get("risk_score",0) < 50)

c1, c2, c3, c4 = st.columns(4)
c1.markdown(f"<div class='metric-card' style='border-left-color:#3498DB;'><div class='metric-label'>Total Screened</div><div class='metric-value'>{len(donors)}</div></div>", unsafe_allow_html=True)
c2.markdown(f"<div class='metric-card' style='border-left-color:#00D2AA;'><div class='metric-label'>Cleared (Safe)</div><div class='metric-value'>{safe}</div></div>", unsafe_allow_html=True)
c3.markdown(f"<div class='metric-card' style='border-left-color:#FFB347;'><div class='metric-label'>Caution</div><div class='metric-value'>{caution}</div></div>", unsafe_allow_html=True)
c4.markdown(f"<div class='metric-card' style='border-left-color:#E74C3C;'><div class='metric-label'>Blocked</div><div class='metric-value'>{blocked}</div></div>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# ── NEW DONOR FORM ──────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>NEW DONOR SCREENING</div>", unsafe_allow_html=True)

with st.form("screening_form"):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<h4 style='color:white;margin-top:0;'>Donor Profile</h4>", unsafe_allow_html=True)
        fname = st.text_input("Full Name *")
        cnic  = st.text_input("CNIC *")
        age   = st.slider("Age", 16, 75, 25)
        bg    = st.selectbox("Blood Group", ["A+","A-","B+","B-","O+","O-","AB+","AB-"])
        last_d = st.date_input("Last Donation Date")
        
    with col2:
        st.markdown("<h4 style='color:white;margin-top:0;'>Medical Questionnaire & Tests</h4>", unsafe_allow_html=True)
        st.markdown("**Pathogen Tests (Check if Positive/Failed):**")
        c2a, c2b, c2c = st.columns(3)
        hiv = c2a.checkbox("HIV")
        hepb= c2b.checkbox("Hep B")
        hepc= c2c.checkbox("Hep C")
        syph= c2a.checkbox("Syphilis")
        mal = c2b.checkbox("Malaria")
        
        st.markdown("**Conditions & Meds:**")
        diab  = st.checkbox("Diabetes")
        hyper = st.checkbox("Hypertension")
        thinn = st.checkbox("On Blood Thinners")
        
    submitted = st.form_submit_button("RUN SCREENING & AI ANALYSIS", use_container_width=True)

if submitted:
    if not fname or not cnic:
        st.error("Name and CNIC are required.")
    else:
        days_since = (datetime.now().date() - last_d).days
        diseases = []
        if hiv: diseases.append("HIV")
        if hepb: diseases.append("Hepatitis B")
        if hepc: diseases.append("Hepatitis C")
        if diab: diseases.append("Diabetes")
        if hyper: diseases.append("Hypertension")
        
        donor_data = {
            "hiv": "failed" if hiv else "passed",
            "hepb": "failed" if hepb else "passed",
            "hepc": "failed" if hepc else "passed",
            "syphilis": "failed" if syph else "passed",
            "malaria": "failed" if mal else "passed"
        }
        
        with st.spinner("AI Expert System analyzing donor profile..."):
            # Call DSA bridges
            screen_res = screen_donor(donor_data)
            risk_res   = calculate_risk_score(age, ",".join(diseases), days_since, 1 if thinn else 0)
            time.sleep(1)
            
            score = risk_res.get("score", 100)
            status = risk_res.get("status", "SAFE")
            if screen_res.get("status") == "BLOCKED":
                score = 0
                status = "BLOCKED"
            
            # Save to DB
            db_donor = {
                "cnic": cnic, "full_name": fname, "blood_group": bg, "age": age,
                "last_donation_date": str(last_d), "on_blood_thinners": 1 if thinn else 0,
                "risk_score": score, "diseases": ",".join(diseases),
                "screening_hiv": donor_data["hiv"], "screening_hepb": donor_data["hepb"],
                "screening_hepc": donor_data["hepc"], "screening_syphilis": donor_data["syphilis"],
                "screening_malaria": donor_data["malaria"]
            }
            add_donor(db_donor)
            add_audit_log("DONOR_SCREENED", st.session_state["email"], hosp_id, "donor", cnic, {"score":score, "status":status})
            
            # Display Result
            st.markdown("<br>", unsafe_allow_html=True)
            if status == "SAFE":
                st.markdown(f"""<div class='glass-card' style='border-color:#00D2AA;text-align:center;'>
                    <h1 style='color:#00D2AA;font-size:3rem;margin:0;'>{score} / 100</h1>
                    <h3 style='color:white;'>✓ DONOR CLEARED FOR DONATION</h3>
                    <p style='color:#95A5A6;'>All screening parameters within safe limits.</p>
                </div>""", unsafe_allow_html=True)
            elif status == "CAUTION":
                st.markdown(f"""<div class='glass-card' style='border-color:#FFB347;text-align:center;'>
                    <h1 style='color:#FFB347;font-size:3rem;margin:0;'>{score} / 100</h1>
                    <h3 style='color:white;'>⚠️ Doctor Approval Required</h3>
                    <p style='color:#95A5A6;'>Donor presents moderate risk factors.</p>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class='glass-card' style='border-color:#E74C3C;text-align:center;animation:pulse-red 1.5s infinite;'>
                    <h1 style='color:#E74C3C;font-size:3rem;margin:0;'>{score} / 100</h1>
                    <h3 style='color:white;'>✗ DONOR PERMANENTLY BLOCKED</h3>
                    <p style='color:#ff416c;'><b>Critical Rule Fired:</b> {screen_res.get('reason', 'High risk factors detected')}</p>
                </div>""", unsafe_allow_html=True)
            
            with st.expander("🤖 AI Expert System — Rule Trace"):
                st.markdown("Forward Chaining: donor facts → rules applied → conclusion reached")
                rules = risk_res.get("rules_fired", []) + screen_res.get("rules_fired", [])
                if rules:
                    for r in rules:
                        st.markdown(f"• `[RULE FIRED]` {r}")
                else:
                    st.markdown("• `[RULE FIRED]` Base clearance rule applied.")
st.markdown("</div>", unsafe_allow_html=True)

# ── COMPATIBILITY & VERIFICATION ────────────────
c1, c2 = st.columns([6,4])

with c1:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>BLOOD GROUP COMPATIBILITY MATRIX</div>", unsafe_allow_html=True)
    
    matrix = {
        "O-": ["O-","O+","A-","A+","B-","B+","AB-","AB+"],
        "O+": ["O+","A+","B+","AB+"],
        "A-": ["A-","A+","AB-","AB+"],
        "A+": ["A+","AB+"],
        "B-": ["B-","B+","AB-","AB+"],
        "B+": ["B+","AB+"],
        "AB-":["AB-","AB+"],
        "AB+":["AB+"]
    }
    groups = ["O-","O+","A-","A+","B-","B+","AB-","AB+"]
    data = []
    for donor in groups:
        row = []
        for rec in groups:
            row.append(1 if rec in matrix[donor] else 0)
        data.append(row)
        
    fig = px.imshow(data, x=groups, y=groups,
                    labels=dict(x="Receiver", y="Donor", color="Compatible"),
                    color_continuous_scale=["#E74C3C","#00D2AA"])
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=0,b=0), coloraxis_showscale=False)
    # Interactive feature
    sel_donor = st.selectbox("Select Donor Group to view Receivers", ["None"] + groups)
    if sel_donor != "None":
        st.markdown(f"**{sel_donor}** can donate to: <span style='color:#00D2AA;'>{', '.join(matrix[sel_donor])}</span>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with c2:
    st.markdown("<div class='glass-card' style='height:100%;'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>BEDSIDE BARCODE VERIFICATION</div>", unsafe_allow_html=True)
    st.markdown("<p style='color:#95A5A6;font-size:0.85rem;'>Scan patient wristband and blood unit barcode prior to transfusion.</p>", unsafe_allow_html=True)
    
    patients = get_patients(hosp_id)
    units = get_blood_units(hosp_id)
    
    p_opts = {f"{p['full_name']} ({p['blood_group']})": p for p in patients}
    u_opts = {f"{u['unit_code']} ({u['blood_group']})": u for u in units}
    
    p_sel = st.selectbox("Patient Wristband", list(p_opts.keys()) if p_opts else ["No patients"])
    u_sel = st.selectbox("Blood Unit Barcode", list(u_opts.keys()) if u_opts else ["No units"])
    
    if st.button("VERIFY COMPATIBILITY", use_container_width=True) and p_opts and u_opts:
        p_data = p_opts[p_sel]
        u_data = u_opts[u_sel]
        
        # Check matrix
        if p_data["blood_group"] in matrix.get(u_data["blood_group"], []):
            st.markdown("""<div style='background:rgba(0,210,170,0.1);border:1px solid #00D2AA;padding:15px;border-radius:8px;text-align:center;margin-top:10px;'>
                <h3 style='color:#00D2AA;margin:0;'>✓ VERIFIED MATCH</h3>
                <p style='color:white;margin:5px 0 0 0;'>Safe to transfuse.</p>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div style='background:rgba(231,76,60,0.1);border:1px solid #E74C3C;padding:15px;border-radius:8px;text-align:center;margin-top:10px;animation:pulse-red 1s infinite;'>
                <h3 style='color:#E74C3C;margin:0;'>✗ MISMATCH DETECTED</h3>
                <p style='color:white;margin:5px 0 0 0;'>FATAL RISK. DO NOT TRANSFUSE.</p>
            </div>""", unsafe_allow_html=True)
            
    st.markdown("</div>", unsafe_allow_html=True)

# ── HISTORY TABLE ───────────────────────────────
with st.expander("View Donor Screening History"):
    if donors:
        rows = ""
        for d in donors:
            score = d.get("risk_score", 0)
            badge = "<span class='badge badge-safe'>SAFE</span>" if score>=80 else ("<span class='badge badge-caution'>CAUTION</span>" if score>=50 else "<span class='badge badge-critical'>BLOCKED</span>")
            rows += f"<tr><td>{d.get('cnic')}</td><td>{d.get('full_name')}</td><td><b>{d.get('blood_group')}</b></td><td>{score}</td><td>{badge}</td><td>{d.get('created_at')[:10]}</td></tr>"
        st.markdown(f"<table class='data-table'><thead><tr><th>CNIC</th><th>Name</th><th>Group</th><th>Score</th><th>Status</th><th>Date</th></tr></thead><tbody>{rows}</tbody></table>", unsafe_allow_html=True)
    else:
        st.info("No donors found.")
