# app.py
"""LIFELINE v6.0 — Intelligent Blood Logistics Network (Pure Python / SQLite Edition)."""

import html

import streamlit as st

from lifeline.auth import session
from lifeline.auth.service import authenticate
from lifeline.bootstrap import ensure_ready
from lifeline.config import get_settings
from lifeline.demo import DEMO_PASSWORD, DEMO_USERS
from utils.styles import alert_banner, get_theme, inject_all_styles, render_ecg, render_login_sidebar

st.set_page_config(
    page_title="LIFELINE — Blood Logistics",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_ready()

# Already signed in with a live session: go straight to the dashboard.
if session.current_user() is not None and not session.is_expired():
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

    flash = st.session_state.pop("_flash", None)
    if flash:
        alert_banner(flash, "warning")

    with st.form("login_form", clear_on_submit=False):
        st.markdown("<h4 style='color:var(--text-primary);'>Sign In</h4>", unsafe_allow_html=True)
        email = st.text_input("Email address", placeholder="Email address", label_visibility="collapsed")
        password = st.text_input("Password", placeholder="Password", type="password", label_visibility="collapsed")

        col_btn, col_theme = st.columns([3, 1])
        with col_btn:
            submitted = st.form_submit_button("→ Access LIFELINE", use_container_width=True)
        with col_theme:
            if st.form_submit_button("Light" if theme == "dark" else "Dark", use_container_width=True):
                st.session_state["theme"] = "light" if theme == "dark" else "dark"
                st.rerun()

    if submitted:
        result = authenticate(email, password)
        if result.ok and result.user is not None:
            session.login(result.user)
            st.switch_page("pages/1_dashboard.py")
            st.stop()
        alert_banner(result.error or "Access Denied — Invalid credentials.", "danger")

    if get_settings().app_env == "demo":
        rows = "".join(
            f"<tr><td>{html.escape(u.email)}</td><td>{html.escape(u.role.label)}</td>"
            f"<td>{html.escape(u.hospital)}</td></tr>"
            for u in DEMO_USERS
        )
        st.markdown(
            f"""<div style="margin-top:16px;opacity:0.85;font-size:0.72rem;text-align:center">
<table class="lifeline-table" style="font-size:0.68rem">
<tr><th>EMAIL</th><th>ROLE</th><th>HOSPITAL</th></tr>{rows}</table>
<p style="color:var(--text-secondary);font-size:0.65rem;text-align:center;margin-top:8px;">
Demo mode — all accounts use password <code>{html.escape(DEMO_PASSWORD)}</code></p></div>""",
            unsafe_allow_html=True,
        )
