"""LIFELINE: sign-in. Everything else lives under pages/."""
from __future__ import annotations

import streamlit as st

from lifeline.auth import session
from lifeline.auth.service import authenticate
from lifeline.bootstrap import ensure_ready
from lifeline.config import get_settings
from lifeline.demo import DEMO_PASSWORD, DEMO_USERS
from lifeline.ui import components as ui
from lifeline.ui.layout import brand_mark, public_page

public_page("Sign in")
ensure_ready()

# Already signed in with a live session: go straight to the dashboard.
if session.current_user() is not None and not session.is_expired():
    st.switch_page("pages/1_dashboard.py")
    st.stop()

_, centre, _ = st.columns([1, 1.6, 1])
with centre:
    ui.render(ui.Html(f'<div class="ll-login">{brand_mark(64)}<div class="ll-brand-name" style="margin-top:12px">LIFE<b>LINE</b></div>'
                      "<p>Intelligent blood logistics · Lahore</p></div>"))
    if flash := st.session_state.pop("_flash", None):
        ui.alert_banner(flash, "warning", title="Signed out")

    with st.form("login_form"):
        email = st.text_input("Email address", key="li_email", autocomplete="username")
        password = st.text_input("Password", type="password", key="li_password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)

    if submitted:
        if not email.strip() or not password:
            ui.alert_banner("Enter your email and password.", "danger", title="Sign in")
        else:
            result = authenticate(email, password)
            if result.ok and result.user is not None:
                session.login(result.user)
                st.switch_page("pages/1_dashboard.py")
                st.stop()
            ui.alert_banner(result.error or "The email or password is not correct.", "danger", title="Sign in failed")

    dark = st.session_state.get("theme") != "light"
    if st.button("Switch to light theme" if dark else "Switch to dark theme", key="li_theme", type="tertiary"):
        st.session_state["theme"] = "light" if dark else "dark"
        st.rerun()

    if get_settings().app_env == "demo":
        ui.alert_banner(f"Demo mode. Every account below uses the password {DEMO_PASSWORD}.", "info", title="Demo accounts")
        ui.render(ui.html_table([{"email": u.email, "role": u.role.label, "hospital": u.hospital} for u in DEMO_USERS],
                                [ui.Col("Email", "email"), ui.Col("Role", "role"), ui.Col("Hospital", "hospital")]))
