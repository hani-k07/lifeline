# pages/10_admin.py
"""Super Admin Panel — LIFELINE v6.0"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime

st.set_page_config(page_title="Admin — LIFELINE", layout="wide")

from utils.styles import (
    inject_all_styles, get_theme, section_header, alert_banner,
    blood_badge, status_pill, styled_table, metric_card,
)
from utils.sidebar import render_sidebar
from utils.database import (
    get_all_hospitals, get_all_users, get_audit_logs,
    get_ai_logs, add_user, add_audit_log,
)

if not st.session_state.get("logged_in"):
    st.switch_page("app.py")
    st.stop()

inject_all_styles(get_theme())
render_sidebar()

_role = st.session_state.get("user_role", "")
_uid = int(st.session_state.get("user_id", 0))

if _role != "admin":
    alert_banner("Access denied. This page is restricted to Super Admins only.", "danger")
    st.stop()

# ── Title Block ──
st.markdown("""
<div style="margin-bottom:24px">
    <h1 style="font-family:'Syne',sans-serif;font-size:1.6rem;margin:0">Super Admin Panel</h1>
    <p style="color:var(--text-secondary);font-size:0.82rem;margin:4px 0 0">
        System management, user administration, and audit trail
    </p>
</div>""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs([
    "User Management",
    "Hospital Network",
    "Audit Logs",
    "AI Usage Logs",
])

with tab1:
    section_header("Registered Users")
    users = get_all_users()

    if users:
        user_rows = []
        for u in users:
            user_rows.append({
                "Name": u.get("name", "—"),
                "Email": u.get("email", "—"),
                "Role": status_pill(u.get("role", "staff")),
                "Hospital": u.get("hospital_name", "Global"),
                "Created": u.get("created_at", "")[:16].replace("T", " ") if u.get("created_at") else "—"
            })
        df_show = pd.DataFrame(user_rows)
        styled_table(df_show)
    else:
        alert_banner("No users registered.", "info")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    section_header("Add New User")

    error_msg = None
    success_msg = None

    with st.form("add_user_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_email = st.text_input("Email *")
            new_name = st.text_input("Full Name *")
            new_role = st.selectbox("Role", ["staff", "hospital", "admin"])
        with col2:
            new_password = st.text_input("Password *", type="password", value="lifeline123")
            hospitals = get_all_hospitals()
            hosp_map = {"None (Global)": None}
            for h in hospitals:
                hosp_map[h["name"]] = h["id"]
            sel_hosp = st.selectbox("Assign Hospital", list(hosp_map.keys()))
            new_hosp_id = hosp_map[sel_hosp]

        submitted = st.form_submit_button("Create User", use_container_width=True)
        if submitted:
            if not new_email or not new_name or not new_password:
                error_msg = "Email, name and password are required."
            else:
                pw_hash = hashlib.sha256(new_password.encode()).hexdigest()
                ok = add_user(new_email, pw_hash, new_role, new_name, new_hosp_id)
                if ok:
                    add_audit_log("USER_CREATED", f"Created user {new_email} with role {new_role}", _uid)
                    success_msg = f"User {new_email} created successfully!"
                else:
                    error_msg = f"Failed — email {new_email} may already exist."

        if success_msg:
            alert_banner(success_msg, "success")
            st.rerun()
        elif error_msg:
            alert_banner(error_msg, "danger")

with tab2:
    hospitals = get_all_hospitals()
    section_header("Hospital Network", f"{len(hospitals)} Facilities")

    if hospitals:
        hosp_rows = []
        for h in hospitals:
            hosp_rows.append({
                "ID": h.get("id", "—"),
                "Hospital Name": h.get("name", "—"),
                "City": h.get("city", "—"),
                "Address": h.get("address", "—"),
                "Phone": h.get("phone", "—"),
                "Coordinates": f"{h.get('latitude', 0.0):.4f}, {h.get('longitude', 0.0):.4f}"
            })
        df_h = pd.DataFrame(hosp_rows)
        styled_table(df_h)

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        section_header("Network Statistics")
        
        from utils.database import get_blood_summary
        total_network_units = 0
        for h in hospitals:
            summary = get_blood_summary(h["id"])
            total_network_units += sum(summary.values())

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(metric_card("Total Hospitals", f"{len(hospitals)}", icon="Hospitals", variant="default"), unsafe_allow_html=True)
        with c2:
            st.markdown(metric_card("Total Network Units", f"{total_network_units}", icon="Stock", variant="default"), unsafe_allow_html=True)
        with c3:
            cities_count = len(set(h.get("city", "Lahore") for h in hospitals))
            st.markdown(metric_card("Cities Covered", f"{cities_count}", icon="Coverage", variant="success"), unsafe_allow_html=True)

with tab3:
    section_header("System Audit Trail")

    limit = st.slider("Show last N entries", 10, 200, 50)
    logs = get_audit_logs(limit)

    if logs:
        log_rows = []
        for log in logs:
            log_rows.append({
                "Timestamp": log.get("timestamp", "")[:16].replace("T", " "),
                "Action": status_pill(log.get("action_type", "—")),
                "Description": log.get("description", "—"),
                "User": log.get("user_name", "—")
            })
        df_logs = pd.DataFrame(log_rows)
        styled_table(df_logs)
    else:
        alert_banner("No audit entries yet.", "info")

with tab4:
    section_header("AI Feature Usage Logs")
    ai_logs = get_ai_logs(50)

    if ai_logs:
        ai_rows = []
        for log in ai_logs:
            ai_rows.append({
                "Timestamp": log.get("created_at", "")[:16].replace("T", " "),
                "Feature": status_pill(log.get("feature", "—")),
                "Input": log.get("input_summary", "—"),
                "Response Preview": log.get("response_preview", "")[:60] + "...",
                "Hospital ID": log.get("hospital_id", "—")
            })
        df_ai = pd.DataFrame(ai_rows)
        styled_table(df_ai)
    else:
        alert_banner("No AI usage logs yet.", "info")

