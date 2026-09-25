# app.py
"""LIFELINE v6.0 — Intelligent Blood Logistics Network (Pure Python / SQLite Edition)."""

import streamlit as st
from lifeline.bootstrap import ensure_ready
from utils.styles import inject_all_styles, get_theme, render_ecg, render_login_sidebar, alert_banner
from utils.auth import validate_login
from utils.database import get_hospital_by_id

st.set_page_config(
    page_title="LIFELINE — Blood Logistics",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_ready()

# Redirect if already logged in
if st.session_state.get("logged_in"):
    st.switch_page("pages/1_dashboard.py")
    st.stop()

render_login_sidebar()
theme = get_theme()
inject_all_styles(theme)

_, col, _ = st.columns([1, 1.6, 1])
with col:
    st.markdown("""
    <div class="login-shell">
        <div class="login-wordmark">LIFE<span>LINE</span></div>
        <div class="login-submark">Intelligent Blood Logistics Network · Lahore</div>
    </div>""", unsafe_allow_html=True)

    render_ecg()

    st.markdown('<div class="glass-hero">', unsafe_allow_html=True)
    
    # We display login status if submitted
    error_msg = None
    
    with st.form("login_form", clear_on_submit=False):
        st.markdown("<h4 style='color:white;'>Sign In</h4>", unsafe_allow_html=True)
        email = st.text_input("", placeholder="Email address", label_visibility="collapsed")
        password = st.text_input("", placeholder="Password", type="password", label_visibility="collapsed")
        
        col_btn, col_theme = st.columns([3, 1])
        with col_btn:
            submitted = st.form_submit_button("→ Access LIFELINE", use_container_width=True)
        with col_theme:
            if st.form_submit_button("Light" if theme == "dark" else "Dark", use_container_width=True):
                st.session_state["theme"] = "light" if theme == "dark" else "dark"
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        if not email or not password:
            error_msg = "Please fill in all fields."
        else:
            user = validate_login(email, password)
            if user:
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = int(user["id"])
                st.session_state["user_email"] = user["email"]
                st.session_state["user_name"] = user["name"]
                st.session_state["user_role"] = user["role"]
                st.session_state["user_hospital_id"] = user["hospital_id"]
                if user["hospital_id"]:
                    hosp = get_hospital_by_id(int(user["hospital_id"]))
                    st.session_state["user_hospital_name"] = hosp["name"] if hosp else "Unknown"
                else:
                    st.session_state["user_hospital_name"] = "Global (All Hospitals)"
                st.switch_page("pages/1_dashboard.py")
                st.stop()
            else:
                error_msg = "Access Denied — Invalid credentials."

    if error_msg:
        alert_banner(error_msg, "danger")

    st.markdown("""
    <div style="margin-top:16px;opacity:0.6;font-size:0.72rem;text-align:center">
    <table class="lifeline-table" style="font-size:0.68rem">
    <tr><th>EMAIL</th><th>ROLE</th><th>HOSPITAL</th></tr>
    <tr><td>admin@lifeline.com</td><td>Super Admin</td><td>Global</td></tr>
    <tr><td>mayo@lifeline.com</td><td>Hospital Admin</td><td>Mayo Hospital</td></tr>
    <tr><td>mayo.worker@lifeline.com</td><td>Staff</td><td>Mayo Hospital</td></tr>
    </table>
    <p style='color:#8892AA;font-size:0.65rem;text-align:center;margin-top:8px;'>
    All accounts: password <code>lifeline123</code></p>
    </div>""", unsafe_allow_html=True)
