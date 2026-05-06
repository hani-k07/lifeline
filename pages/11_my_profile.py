import streamlit as st
import pandas as pd
from utils.supabase_client import get_hospital_by_id, change_password, get_audit_logs, add_audit_log
from utils.sidebar import render_sidebar

if not st.session_state.get("logged_in"):
    st.warning("Please login first.")
    st.stop()

st.set_page_config(page_title="My Profile - LIFELINE", layout="wide")
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
.profile-label { color:#95A5A6; font-size:0.8rem; text-transform:uppercase; margin-bottom:2px; }
.profile-value { color:white; font-size:1.1rem; font-weight:600; margin-bottom:15px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='color:white;'>👤 My Profile</h1>", unsafe_allow_html=True)

# Fetch current user details from session and DB
user_id = st.session_state.get("user_id")
email = st.session_state.get("email")
role = st.session_state.get("user_role")
hosp_id = st.session_state.get("hospital_id")
fullname = st.session_state.get("full_name")

hospital_name = "System Wide"
if hosp_id:
    hosp = get_hospital_by_id(hosp_id)
    hospital_name = hosp.get('name', 'Unknown')

# --- FEATURE A: VIEW MY PROFILE ---
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>ACCOUNT INFORMATION</div>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.markdown("<div class='profile-label'>Full Name</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='profile-value'>{fullname}</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='profile-label'>Email Address</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='profile-value'>{email}</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='profile-label'>Assigned Hospital</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='profile-value'>{hospital_name}</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='profile-label'>Department</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='profile-value'>{st.session_state.get('department', 'Blood Bank')}</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='profile-label'>Shift</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='profile-value'>{st.session_state.get('shift', 'Morning')}</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='profile-label'>Network Role</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='profile-value'>{role.replace('_', ' ').title()}</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='profile-label'>User ID</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='profile-value'>{user_id}</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# --- FEATURE B: CHANGE MY PASSWORD ---
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>SECURITY — CHANGE PASSWORD</div>", unsafe_allow_html=True)

with st.form("change_pass_form"):
    curr_pass = st.text_input("Current Password", type="password")
    new_pass = st.text_input("New Password (min 8 chars)", type="password")
    conf_pass = st.text_input("Confirm New Password", type="password")
    
    if st.form_submit_button("UPDATE PASSWORD"):
        if not curr_pass or not new_pass or not conf_pass:
            st.error("All fields are required")
        elif new_pass != conf_pass:
            st.error("New passwords do not match")
        elif len(new_pass) < 8:
            st.error("New password must be at least 8 characters")
        elif new_pass == curr_pass:
            st.error("New password cannot be the same as current password")
        else:
            if change_password(user_id, curr_pass, new_pass):
                add_audit_log("PASSWORD_CHANGED", email, hosp_id, "user", user_id, "User changed own password")
                st.success("✓ Password changed successfully! Please login again.")
                st.session_state.clear()
                st.rerun()
            else:
                st.error("Incorrect current password")

st.markdown("</div>", unsafe_allow_html=True)

# --- FEATURE C: MY ACTIVITY LOG ---
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>RECENT ACTIVITY LOG</div>", unsafe_allow_html=True)

my_logs = get_audit_logs(limit=20, actor_email=email)
if my_logs:
    df_logs = pd.DataFrame(my_logs)
    st.dataframe(df_logs[["created_at", "action", "details"]], hide_index=True, use_container_width=True)
else:
    st.info("No recent activity found.")

st.markdown("</div>", unsafe_allow_html=True)
