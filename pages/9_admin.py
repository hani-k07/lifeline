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

from utils.styles import get_glass_css
st.markdown(get_glass_css(), unsafe_allow_html=True)

st.markdown("<h1 style='color:white;'>🛡️ Super Admin Control Panel</h1>", unsafe_allow_html=True)

# --- Data Fetching ---
all_hospitals = get_hospitals()
all_workers = get_all_users() # Returns all except super_admin
active_workers = [w for w in all_workers if w['is_active'] == 1]
inactive_workers = [w for w in all_workers if w['is_active'] == 0]

# --- FEATURE E: OVERVIEW ---
st.markdown("<div class='section-header'>NETWORK OVERVIEW</div>", unsafe_allow_html=True)
total_hospitals = len(all_hospitals)
total_workers = len(all_workers)
active_count = len(active_workers)
inactive_count = len(inactive_workers)

col1, col2, col3, col4 = st.columns(4)
col1.metric("🏥 Total Hospitals", total_hospitals)
col2.metric("👥 Total Workers",   total_workers)
col3.metric("✅ Active Users",    active_count)
col4.metric("❌ Inactive Users",  inactive_count)

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
    # Header row
    h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([3,2,2,2,3])
    h_col1.markdown("**Hospital Name**")
    h_col2.markdown("**City**")
    h_col3.markdown("**Type**")
    h_col4.markdown("**Status**")
    h_col5.markdown("**Actions**")
    st.markdown("<hr style='margin:10px 0; opacity:0.2'>", unsafe_allow_html=True)

    for hosp in all_hospitals:
        col_name, col_city, col_type, col_status, col_actions = st.columns([3,2,2,2,3])
        col_name.write(hosp["name"])
        col_city.write(hosp.get("city", "Lahore"))
        col_type.write(hosp.get("hospital_type", "Public"))
        
        status_color = "#00D2AA" if hosp.get("status") == "active" else "#E74C3C"
        col_status.markdown(f"<span style='color:{status_color}'>{hosp.get('status', 'active').title()}</span>", unsafe_allow_html=True)
        
        with col_actions:
            if st.button("✏️ Edit", key=f"edit_{hosp['id']}"):
                st.session_state[f"editing_{hosp['id']}"] = True
        
        # Edit expander (appears below row when Edit clicked)
        if st.session_state.get(f"editing_{hosp['id']}", False):
            with st.expander(f"Edit — {hosp['name']}", expanded=True):
                new_address = st.text_input("Address", value=hosp.get("address", ""), key=f"addr_{hosp['id']}")
                new_contact = st.text_input("Contact Number", value=hosp.get("contact_number", ""), key=f"contact_{hosp['id']}")
                new_status = st.selectbox(
                    "Status",
                    options=["active", "inactive", "maintenance"],
                    index=["active","inactive","maintenance"].index(hosp.get("status","active")),
                    key=f"status_{hosp['id']}"
                )
                new_h_type = st.selectbox(
                    "Hospital Type",
                    options=["Public", "Private", "Teaching"],
                    index=["Public", "Private", "Teaching"].index(hosp.get("hospital_type","Public")),
                    key=f"type_{hosp['id']}"
                )
                
                save_col, cancel_col = st.columns(2)
                if save_col.button("💾 Save", key=f"save_{hosp['id']}"):
                    success = update_hospital(hosp["id"], {
                        "address":        new_address,
                        "contact_number": new_contact,
                        "status":         new_status,
                        "hospital_type":  new_h_type
                    })
                    if success:
                        st.success(f"✓ {hosp['name']} updated")
                        st.session_state[f"editing_{hosp['id']}"] = False
                        st.rerun()
                    else:
                        st.error("Update failed")
                
                if cancel_col.button("✖ Cancel", key=f"cancel_{hosp['id']}"):
                    st.session_state[f"editing_{hosp['id']}"] = False
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
    # Header row
    w_col1, w_col2, w_col3, w_col4, w_col5 = st.columns([2,3,2,2,3])
    w_col1.markdown("**Full Name**")
    w_col2.markdown("**Email**")
    w_col3.markdown("**Role**")
    w_col4.markdown("**Hospital**")
    w_col5.markdown("**Actions**")
    st.markdown("<hr style='margin:10px 0; opacity:0.2'>", unsafe_allow_html=True)

    for worker in filtered_workers:
        text_style = "text-decoration: line-through; color: #95A5A6;" if worker['is_active'] == 0 else "color: white;"
        col_name, col_email, col_role, col_hosp, col_actions = st.columns([2,3,2,2,3])
        
        col_name.markdown(f"<div style='{text_style}'>{worker['full_name']}</div>", unsafe_allow_html=True)
        col_email.markdown(f"<div style='{text_style}'>{worker['email']}</div>", unsafe_allow_html=True)
        
        # Inline role change selectbox
        with col_role:
            current_role = worker.get("role", "staff")
            new_role = st.selectbox(
                "",
                options=["staff", "hospital_admin"],
                index=0 if current_role == "staff" else 1,
                key=f"role_{worker['id']}",
                label_visibility="collapsed"
            )
            if new_role != current_role:
                if update_user_role(worker["id"], new_role):
                    st.success(f"✓ Role updated to {new_role}")
                    st.rerun()
        
        col_hosp.write(worker.get("hospital_name", "—"))
        
        with col_actions:
            ca1, ca2 = st.columns(2)
            if ca1.button("🔑 Reset", key=f"reset_{worker['id']}", help="Reset password to lifeline123"):
                reset_user_password(worker["id"], "lifeline123")
                st.success("Reset to lifeline123")
            
            if worker['is_active'] == 1:
                if ca2.button("🚫 Deactivate", key=f"deact_u_{worker['id']}"):
                    deactivate_user(worker['id'])
                    st.rerun()
            else:
                if ca2.button("✅ Reactivate", key=f"act_u_{worker['id']}"):
                    reactivate_user(worker['id'])
                    st.rerun()
else:
    st.info("No workers found matching filters.")
st.markdown("</div>", unsafe_allow_html=True)
