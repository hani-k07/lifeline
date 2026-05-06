import streamlit as st
import pandas as pd
import plotly.express as px
import uuid
from datetime import datetime
from utils.supabase_client import (
    get_hospital_by_id, get_workers_by_hospital, update_hospital,
    auth_signup, update_user_shift, deactivate_user, reset_user_password,
    get_hospital_stats, add_audit_log
)
from utils.sidebar import render_sidebar

# Access Control
role = st.session_state.get("user_role", "staff")
if role not in ["super_admin", "hospital_admin"]:
    st.markdown("""
    <style>
    .glass-card {
        background: rgba(20,20,35,0.7);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 16px;
        text-align: center;
    }
    </style>
    <div class='glass-card' style='border-color:rgba(255,65,108,0.4);'>
        <h2 style='color:white;'>🚫 Access Denied</h2>
        <p style='color:#95A5A6;'>You do not have permission to view this page. Hospital Admin only.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

st.set_page_config(page_title="Hospital Management - LIFELINE", layout="wide")
render_sidebar()

st.markdown("""
<style>
.section-header {
    font-size:0.8rem; font-weight:600; color:#ff416c;
    text-transform:uppercase; letter-spacing:2px;
    margin-bottom:20px; padding-bottom:10px;
    border-bottom:1px solid rgba(255,65,108,0.2);
}
.glass-card {
    background: rgba(20,20,35,0.7);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
}
.metric-card {
    background: rgba(20,20,35,0.8);
    border: 1px solid rgba(255,255,255,0.06);
    border-left: 3px solid #ff416c;
    border-radius: 12px;
    padding: 18px 20px;
}
.metric-value {
    font-size:1.8rem; font-weight:700;
    background: linear-gradient(135deg,#ff416c,#ff4b2b);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.metric-label { font-size:0.7rem; color:#95A5A6; text-transform:uppercase; letter-spacing:1.5px; }
</style>
""", unsafe_allow_html=True)

# Hospital ID for current user
hosp_id = st.session_state.get("hospital_id")
if not hosp_id and role == "super_admin":
    all_hospitals = {h['name']: h['id'] for h in get_hospital_by_id("")} # Dummy call to get list
    # For super admin, let them pick a hospital to manage
    h_list = {h['name']: h['id'] for h in get_hospitals()}
    selected_h_name = st.selectbox("Select Hospital to Manage", list(h_list.keys()))
    hosp_id = h_list[selected_h_name]

if not hosp_id:
    st.error("No hospital associated with your account.")
    st.stop()

hospital = get_hospital_by_id(hosp_id)
stats = get_hospital_stats(hosp_id)

st.markdown(f"<h1 style='color:white;'>🏥 {hospital['name']} Management</h1>", unsafe_allow_html=True)

# --- FEATURE A: MY HOSPITAL OVERVIEW ---
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>FACILITY OVERVIEW</div>", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"<div class='metric-card'><div class='metric-label'>Total Workers</div><div class='metric-value'>{stats['worker_count']}</div></div>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<div class='metric-card'><div class='metric-label'>Blood Units</div><div class='metric-value'>{stats['unit_count']}</div></div>", unsafe_allow_html=True)
with col3:
    st.markdown(f"<div class='metric-card'><div class='metric-label'>Active Contracts</div><div class='metric-value'>{stats['active_contracts']}</div></div>", unsafe_allow_html=True)
with col4:
    st.markdown(f"<div class='metric-card'><div class='metric-label'>Status</div><div class='metric-value' style='background:none; -webkit-text-fill-color:{'#00D2AA' if hospital['status']=='active' else '#FFB347'};'>{hospital['status'].upper()}</div></div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
with st.expander("📝 Edit Hospital Details"):
    with st.form("edit_hosp_form"):
        new_addr = st.text_input("Address", value=hospital['address'])
        new_phone = st.text_input("Contact Number", value=hospital['contact_number'])
        if st.form_submit_button("UPDATE FACILITY INFO"):
            if update_hospital(hosp_id, {'address': new_addr, 'contact_number': new_phone}):
                add_audit_log("HOSPITAL_UPDATED", st.session_state["email"], hosp_id, "hospital", hosp_id, "Info updated")
                st.success("✓ Facility information updated")
                st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

# --- FEATURE B: ADD NEW WORKER ---
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>ADD NEW STAFF MEMBER</div>", unsafe_allow_html=True)
with st.form("add_staff_form"):
    r1c1, r1c2, r1c3 = st.columns(3)
    w_name = r1c1.text_input("Full Name *")
    w_email = r1c2.text_input("Email *")
    w_pass = r1c3.text_input("Temporary Password *", value="staff123")
    
    r2c1, r2c2, r2c3 = st.columns(3)
    w_dept = r2c1.selectbox("Department", ["Blood Bank", "ICU", "Emergency", "Lab", "Admin"])
    w_shift = r2c2.selectbox("Shift", ["Morning", "Evening", "Night"])
    w_phone = r2c3.text_input("Phone Number")
    
    w_emp_id = st.text_input("Employee ID (Optional)")
    
    if st.form_submit_button("REGISTER STAFF"):
        if not w_name or not w_email or not w_pass:
            st.error("Name, Email, and Password are required")
        else:
            final_emp_id = w_emp_id if w_emp_id else f"EMP-{str(uuid.uuid4())[:6].upper()}"
            success = auth_signup(w_email, w_pass, w_name, "staff", hosp_id, 
                                 phone_number=w_phone, employee_id=final_emp_id, 
                                 department=w_dept, shift=w_shift)
            if success:
                add_audit_log("STAFF_ADDED", st.session_state["email"], hosp_id, "user", w_email, f"{w_name} added to {w_dept}")
                st.success(f"✓ Staff member {w_name} added")
                st.info(f"Temporary password: {w_pass} - Please share with staff member.")
                st.rerun()
            else:
                st.error("Error: Email might already exist.")
st.markdown("</div>", unsafe_allow_html=True)

# --- FEATURE C: MANAGE MY WORKERS ---
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>MANAGE STAFF</div>", unsafe_allow_html=True)

workers = get_workers_by_hospital(hosp_id)
if workers:
    for w in workers:
        with st.container():
            st.markdown(f"""
            <div style='background:rgba(255,255,255,0.03); padding:10px; border-radius:8px; margin-bottom:5px;'>
                <div style='display:flex; justify-content:space-between;'>
                    <div>
                        <strong>{w['full_name']}</strong> ({w['email']}) <br>
                        <small>{w['department']} | {w['shift']} Shift | {w['employee_id']}</small>
                    </div>
                    <div style='text-align:right;'>
                        <span class='badge {"badge-safe" if w["is_active"]==1 else "badge-blocked"}'>
                            {"Active" if w["is_active"]==1 else "Inactive"}
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                new_s = st.selectbox("Shift", ["Morning", "Evening", "Night"], index=["Morning", "Evening", "Night"].index(w['shift']), key=f"s_{w['id']}")
            with c2:
                new_d = st.selectbox("Dept", ["Blood Bank", "ICU", "Emergency", "Lab", "Admin"], index=["Blood Bank", "ICU", "Emergency", "Lab", "Admin"].index(w['department']), key=f"d_{w['id']}")
            
            if new_s != w['shift'] or new_d != w['department']:
                if st.button("Update", key=f"upd_{w['id']}"):
                    update_user_shift(w['id'], new_s, new_d)
                    st.rerun()
                    
            if c3.button("Reset Pass", key=f"res_{w['id']}"):
                reset_user_password(w['id'], "staff123")
                st.info(f"Password reset to: staff123")
            
            if w['id'] != st.session_state.get("user_id"):
                if w['is_active'] == 1:
                    if c4.button("Deactivate", key=f"deact_{w['id']}"):
                        deactivate_user(w['id'])
                        st.rerun()
else:
    st.info("No staff members found.")
st.markdown("</div>", unsafe_allow_html=True)

# --- FEATURE D: SHIFT SUMMARY ---
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>STAFF DISTRIBUTION</div>", unsafe_allow_html=True)

if workers:
    df_w = pd.DataFrame(workers)
    shift_counts = df_w['shift'].value_counts().to_dict()
    
    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Morning", shift_counts.get("Morning", 0))
    sc2.metric("Evening", shift_counts.get("Evening", 0))
    sc3.metric("Night", shift_counts.get("Night", 0))
    
    st.markdown("<br>", unsafe_allow_html=True)
    if stats['departments']:
        df_dept = pd.DataFrame(list(stats['departments'].items()), columns=['Department', 'Count'])
        fig = px.pie(df_dept, values='Count', names='Department', hole=0.4, title="Staff by Department")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)
