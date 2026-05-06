import streamlit as st
import pandas as pd
import plotly.express as px
import uuid
import hashlib
from datetime import datetime
from utils.supabase_client import (
    get_hospitals, get_all_users, get_workers_by_hospital, add_hospital, 
    update_hospital, deactivate_user, reactivate_user, 
    reset_user_password, update_user_role, auth_signup, add_audit_log
)
from utils.sidebar import render_sidebar

# Access Control
role = st.session_state.get("user_role", "staff")
if role != "super_admin":
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
        <p style='color:#95A5A6;'>You do not have permission to view this page. Super Admin only.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

st.set_page_config(page_title="Super Admin - LIFELINE", layout="wide")
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

st.markdown("<h1 style='color:white;'>🛡️ Super Admin Control Panel</h1>", unsafe_allow_html=True)

# --- Data Fetching ---
all_hospitals = get_hospitals()
all_workers = get_all_users() # Returns all except super_admin
active_workers = [w for w in all_workers if w['is_active'] == 1]
inactive_workers = [w for w in all_workers if w['is_active'] == 0]

# --- FEATURE E: OVERVIEW ---
st.markdown("<div class='section-header'>NETWORK OVERVIEW</div>", unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"<div class='metric-card'><div class='metric-label'>Total Hospitals</div><div class='metric-value'>{len(all_hospitals)}</div></div>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<div class='metric-card'><div class='metric-label'>Total Workers</div><div class='metric-value'>{len(all_workers)}</div></div>", unsafe_allow_html=True)
with col3:
    st.markdown(f"<div class='metric-card' style='border-left-color:#00D2AA;'><div class='metric-label'>Active Users</div><div class='metric-value'>{len(active_workers)}</div></div>", unsafe_allow_html=True)
with col4:
    st.markdown(f"<div class='metric-card' style='border-left-color:#95A5A6;'><div class='metric-label'>Inactive Users</div><div class='metric-value'>{len(inactive_workers)}</div></div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    if all_workers:
        df_workers = pd.DataFrame(all_workers)
        worker_counts = df_workers['hospital_name'].value_counts().reset_index()
        worker_counts.columns = ['Hospital', 'Workers']
        fig1 = px.bar(worker_counts, x='Hospital', y='Workers', title="Workers per Hospital", 
                     color_discrete_sequence=['#ff416c'])
        fig1.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig1, use_container_width=True)
with chart_col2:
    if all_workers:
        role_counts = df_workers['role'].value_counts().reset_index()
        role_counts.columns = ['Role', 'Count']
        fig2 = px.pie(role_counts, values='Count', names='Role', title="Role Distribution",
                     color_discrete_sequence=['#2980B9', '#00D2AA', '#F39C12'])
        fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white')
        st.plotly_chart(fig2, use_container_width=True)

# --- FEATURE A: ADD NEW HOSPITAL ---
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>ADD NEW HOSPITAL</div>", unsafe_allow_html=True)
with st.form("add_hospital_form"):
    r1c1, r1c2, r1c3 = st.columns(3)
    h_name = r1c1.text_input("Hospital Name *")
    h_city = r1c2.text_input("City", value="Lahore")
    h_addr = r1c3.text_input("Address")
    
    r2c1, r2c2, r2c3 = st.columns(3)
    h_phone = r2c1.text_input("Contact Number")
    h_lat = r2c2.number_input("Latitude", value=31.5734, format="%.4f")
    h_lng = r2c3.number_input("Longitude", value=74.3044, format="%.4f")
    
    r3c1, r3c2 = st.columns(2)
    h_status = r3c1.selectbox("Status", ["active", "inactive", "maintenance"])
    h_type = r3c2.selectbox("Hospital Type", ["Public", "Private", "Teaching"])
    
    if st.form_submit_button("ADD HOSPITAL TO NETWORK"):
        if not h_name:
            st.error("Hospital Name is required")
        elif not (30 <= h_lat <= 33):
            st.error("Latitude must be between 30-33 (Lahore range)")
        elif not (73 <= h_lng <= 75):
            st.error("Longitude must be between 73-75 (Lahore range)")
        else:
            h_id = add_hospital({
                'name': h_name, 'city': h_city, 'address': h_addr,
                'contact_number': h_phone, 'lat': h_lat, 'lng': h_lng,
                'hospital_type': h_type, 'status': h_status
            })
            if h_id:
                add_audit_log("HOSPITAL_ADDED", st.session_state["email"], None, "hospital", h_id, h_name)
                st.success(f"✓ {h_name} added to network")
                st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

# --- FEATURE B: MANAGE ALL HOSPITALS ---
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>MANAGE HOSPITALS</div>", unsafe_allow_html=True)

if all_hospitals:
    for h in all_hospitals:
        with st.expander(f"🏥 {h['name']} ({h['city']}) - {h['hospital_type']} | Status: {h['status']}"):
            col1, col2 = st.columns([2, 1])
            with col1:
                st.write(f"**Address:** {h['address']}")
                st.write(f"**Contact:** {h['contact_number']}")
                st.write(f"**Coordinates:** {h['lat']}, {h['lng']}")
            
            with col2:
                if st.button("Edit Details", key=f"edit_h_{h['id']}"):
                    st.session_state[f"editing_h_{h['id']}"] = True
                
                if h['status'] != 'inactive':
                    if st.button("Deactivate", key=f"deact_h_{h['id']}"):
                        update_hospital(h['id'], {'status': 'inactive'})
                        add_audit_log("HOSPITAL_DEACTIVATED", st.session_state["email"], h['id'], "hospital", h['id'], h['name'])
                        st.rerun()
            
            if st.session_state.get(f"editing_h_{h['id']}", False):
                st.markdown("---")
                with st.form(f"form_edit_{h['id']}"):
                    new_addr = st.text_input("Address", value=h['address'])
                    new_contact = st.text_input("Contact", value=h['contact_number'])
                    new_status = st.selectbox("Status", ["active", "inactive", "maintenance"], 
                                             index=["active", "inactive", "maintenance"].index(h['status']))
                    if st.form_submit_button("SAVE CHANGES"):
                        update_hospital(h['id'], {'address': new_addr, 'contact_number': new_contact, 'status': new_status})
                        st.session_state[f"editing_h_{h['id']}"] = False
                        st.success("Hospital updated")
                        st.rerun()
                    if st.form_submit_button("CANCEL"):
                        st.session_state[f"editing_h_{h['id']}"] = False
                        st.rerun()
else:
    st.info("No hospitals found.")
st.markdown("</div>", unsafe_allow_html=True)

# --- FEATURE C: ADD NEW WORKER ---
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>ADD NEW WORKER</div>", unsafe_allow_html=True)
with st.form("add_worker_form"):
    r1c1, r1c2, r1c3 = st.columns(3)
    w_name = r1c1.text_input("Full Name *")
    w_email = r1c2.text_input("Email *")
    w_pass = r1c3.text_input("Password *", type="password")
    
    r2c1, r2c2, r2c3 = st.columns(3)
    w_role = r2c1.selectbox("Role", ["hospital_admin", "staff"])
    hosp_options = {h['name']: h['id'] for h in all_hospitals}
    w_hosp = r2c2.selectbox("Hospital *", options=list(hosp_options.keys()))
    w_phone = r2c3.text_input("Phone Number")
    
    w_emp_id = st.text_input("Employee ID (Auto-generated if empty)")
    
    if st.form_submit_button("ADD WORKER TO SYSTEM"):
        if not w_name or not w_email or not w_pass:
            st.error("Name, Email, and Password are required")
        elif len(w_pass) < 8:
            st.error("Password must be at least 8 characters")
        else:
            final_emp_id = w_emp_id if w_emp_id else f"EMP-{str(uuid.uuid4())[:6].upper()}"
            hid = hosp_options[w_hosp]
            success = auth_signup(w_email, w_pass, w_name, w_role, hid, phone_number=w_phone, employee_id=final_emp_id)
            if success:
                add_audit_log("USER_ADDED", st.session_state["email"], hid, "user", w_email, f"{w_name} added as {w_role}")
                st.success(f"✓ {w_name} added to {w_hosp}")
                st.rerun()
            else:
                st.error("Error: Email might already exist.")
st.markdown("</div>", unsafe_allow_html=True)

# --- FEATURE D: MANAGE ALL WORKERS ---
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>MANAGE ALL WORKERS</div>", unsafe_allow_html=True)

col_f1, col_f2, col_f3 = st.columns(3)
f_hosp = col_f1.selectbox("Filter by Hospital", ["All"] + list(hosp_options.keys()), index=0)
f_role = col_f2.selectbox("Filter by Role", ["All", "hospital_admin", "staff"])
f_search = col_f3.text_input("Search by Name")

filtered_workers = all_workers
if f_hosp != "All":
    filtered_workers = [w for w in filtered_workers if w['hospital_name'] == f_hosp]
if f_role != "All":
    filtered_workers = [w for w in filtered_workers if w['role'] == f_role]
if f_search:
    filtered_workers = [w for w in filtered_workers if f_search.lower() in w['full_name'].lower()]

if filtered_workers:
    for w in filtered_workers:
        bg_color = "rgba(41, 128, 185, 0.1)" if w['role'] == "hospital_admin" else "rgba(255,255,255,0.03)"
        text_style = "text-decoration: line-through; color: #95A5A6;" if w['is_active'] == 0 else "color: white;"
        
        with st.container():
            st.markdown(f"""
            <div style='background:{bg_color}; padding:10px; border-radius:8px; margin-bottom:5px; border:1px solid rgba(255,255,255,0.05);'>
                <div style='display:flex; justify-content:space-between; align-items:center;'>
                    <div style='{text_style}'>
                        <strong>{w['full_name']}</strong> ({w['email']}) <br>
                        <small>{w['role']} @ {w['hospital_name']}</small>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                current_roles = ["hospital_admin", "staff"]
                new_r = st.selectbox("Change Role", current_roles, index=current_roles.index(w['role']), key=f"role_sel_{w['id']}")
                if new_r != w['role']:
                    update_user_role(w['id'], new_r)
                    st.rerun()
            
            if c2.button("Reset Password", key=f"reset_{w['id']}"):
                reset_user_password(w['id'], "lifeline123")
                st.success(f"Password reset to: lifeline123")
                
            if w['is_active'] == 1:
                if c3.button("Deactivate", key=f"deact_u_{w['id']}"):
                    deactivate_user(w['id'])
                    st.rerun()
            else:
                if c3.button("Reactivate", key=f"act_u_{w['id']}"):
                    reactivate_user(w['id'])
                    st.rerun()
else:
    st.info("No workers found matching filters.")
st.markdown("</div>", unsafe_allow_html=True)
