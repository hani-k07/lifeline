# LIFELINE v5.0 — Intelligent Blood Logistics Network
# =====================================================
# SETUP:
#   1. pip install -r requirements.txt
#   2. python setup_database.py
#   3. streamlit run app.py
#
# LOGIN CREDENTIALS:
#   admin@lifeline.com    / lifeline123  (Super Admin)
#   mayo@lifeline.com     / lifeline123  (Hospital Admin)
#   services@lifeline.com / lifeline123  (Hospital Admin)
#   staff@lifeline.com    / lifeline123  (Staff)

import streamlit as st
import os
import base64
import time
from utils.supabase_client import auth_login
from utils.helpers import pakistan_time
from utils.sidebar import render_sidebar

st.set_page_config(
    page_title="LIFELINE — Blood Logistics Network",
    layout="wide",
    initial_sidebar_state="expanded"
)

from utils.styles import get_glass_css
st.markdown(get_glass_css(), unsafe_allow_html=True)

# ── SESSION STATE ──────────────────────────────
for key, val in [("logged_in", False), ("user_role", None), ("hospital_id", None),
                 ("email", None), ("full_name", None), ("user_id", None)]:
    if key not in st.session_state:
        st.session_state[key] = val

# ── LOGIN PAGE ─────────────────────────────────
if not st.session_state["logged_in"]:
    st.markdown("""<style>[data-testid="stSidebar"]{display:none;}</style>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.6, 1])
    with col2:
        # Logo
        if os.path.exists("logo.png"):
            with open("logo.png", "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            st.markdown(f"""<div style='text-align:center; margin-bottom:20px;'>
                <img src='data:image/png;base64,{b64}' style='max-width:220px; border-radius:16px;
                box-shadow:0 10px 40px rgba(255,65,108,0.3);'>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div style='text-align:center; margin-bottom:20px;'>
                <h1 style='color:white; font-size:3rem; margin:0;'>LIFELINE</h1>
            </div>""", unsafe_allow_html=True)

        st.markdown("""<p style='text-align:center; color:#95A5A6; font-size:1rem;
            margin-bottom:28px;'>Intelligent Blood Logistics Network — Lahore</p>""",
            unsafe_allow_html=True)

        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-header'>SECURE AUTHENTICATION</div>", unsafe_allow_html=True)
        with st.form("login_form", clear_on_submit=False):
            email_in = st.text_input("Network ID (Email)", placeholder="admin@lifeline.com")
            pass_in  = st.text_input("Access Key", type="password", placeholder="••••••••••")
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button("AUTHENTICATE SESSION", use_container_width=True)

        if submitted:
            data = auth_login(email_in, pass_in)
            if data == "DEACTIVATED":
                st.error("Your account has been deactivated.")
            elif data:
                st.session_state.update({
                    "logged_in":   True,
                    "user_role":   data["role"],
                    "hospital_id": data["hospital_id"],
                    "email":       email_in,
                    "full_name":   data.get("full_name","User"),
                    "user_id":     data.get("id",""),
                    "department":  data.get("department", "Blood Bank"),
                    "shift":       data.get("shift", "Morning"),
                })
                st.rerun()
            else:
                st.error("Access Denied — Invalid credentials.")
        st.markdown("</div>", unsafe_allow_html=True)

        # Credential hints
        st.markdown("""
        <div class='glass-card' style='padding:18px;'>
          <div class='section-header'>DEMO CREDENTIALS</div>
          <table class='data-table'>
            <tr><th>Email</th><th>Password</th><th>Role</th></tr>
            <tr><td>admin@lifeline.com</td><td>lifeline123</td><td><span class='badge badge-critical'>Super Admin</span></td></tr>
            <tr><td>mayo@lifeline.com</td><td>lifeline123</td><td><span class='badge badge-info'>Hospital Admin</span></td></tr>
            <tr><td>staff@lifeline.com</td><td>lifeline123</td><td><span class='badge badge-caution'>Staff</span></td></tr>
          </table>
        </div>
        """, unsafe_allow_html=True)

# ── AUTHENTICATED LAYOUT ───────────────────────
else:
    role     = st.session_state["user_role"]
    hosp_id  = st.session_state["hospital_id"]
    email    = st.session_state["email"] or ""
    fullname = st.session_state["full_name"] or "User"

    # Sidebar
    render_sidebar()

    # Home page content
    st.markdown("""<div class='glass-card' style='text-align:center; padding:40px;'>
        <h1 style='color:white; font-size:2.5rem; margin:0;'>Welcome to LIFELINE</h1>
        <p style='color:#95A5A6; font-size:1.1rem; margin-top:12px;'>
            Select a module from the sidebar to begin.</p>
        <p style='color:#ff416c; font-size:0.9rem; margin-top:8px;'>
            Intelligent Blood Logistics Network — Lahore, Pakistan</p>
    </div>""", unsafe_allow_html=True)
