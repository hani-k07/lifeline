# utils/sidebar.py
import html

import streamlit as st

from lifeline.auth.roles import ADMIN_ROLES, ALL_ROLES, Role
from lifeline.bootstrap import ensure_ready

PAGE_LINKS = [
    ("pages/1_dashboard.py",   "Dashboard",   ALL_ROLES),
    ("pages/2_inventory.py",   "Inventory",   ALL_ROLES),
    ("pages/3_emergency.py",   "Emergency",   ALL_ROLES),
    ("pages/4_exchange.py",    "Exchange",    ALL_ROLES),
    ("pages/5_screening.py",   "Screening",   ALL_ROLES),
    ("pages/6_contracts.py",   "Contracts",   ALL_ROLES),
    ("pages/7_transfusion.py", "Transfusion", ALL_ROLES),
    ("pages/8_analytics.py",   "Analytics",   ALL_ROLES),
    ("pages/9_ai_center.py",   "AI Center",   ADMIN_ROLES),
    ("pages/10_admin.py",      "Admin Panel", (Role.SUPER_ADMIN,)),
]

def render_sidebar() -> None:
    ensure_ready()
    role  = st.session_state.get("user_role", "")
    name  = st.session_state.get("user_name", "User")
    hosp  = st.session_state.get("user_hospital_name", "Global")
    theme = st.session_state.get("theme", "dark")

    with st.sidebar:
        st.markdown(f"""
        <div style="padding:8px 0 16px">
            <div class="sidebar-logo">LIFELINE</div>
            <div style="font-size:0.78rem;color:var(--text-secondary);margin:2px 0">{html.escape(name)}</div>
            <div style="font-size:0.72rem;color:var(--text-secondary)">{html.escape(hosp)}</div>
            <span class="sidebar-role-badge">{html.escape(role.upper())}</span>
        </div>""", unsafe_allow_html=True)

        st.divider()

        for path, label, allowed_roles in PAGE_LINKS:
            if role in allowed_roles:
                st.page_link(path, label=label)

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Light" if theme == "dark" else "Dark", use_container_width=True, key="sidebar_theme_btn"):
                st.session_state["theme"] = "light" if theme == "dark" else "dark"
                st.rerun()
        with col2:
            if st.button("Logout", use_container_width=True, key="sidebar_logout_btn"):
                st.session_state.clear()
                st.switch_page("app.py")

        st.markdown("""
        <div style="margin-top:32px;text-align:center;font-size:0.65rem;color:var(--text-secondary);
                    font-family:'JetBrains Mono',monospace">
            LIFELINE v6.0 · NASTP-NIIT<br>Dept. of Artificial Intelligence
        </div>""", unsafe_allow_html=True)
