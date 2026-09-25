# pages/6_contracts.py
"""Vendor Contracts — LIFELINE v6.0"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Contracts — LIFELINE", layout="wide")

from utils.styles import (
    inject_all_styles, get_theme, section_header, alert_banner,
    blood_badge, status_pill, styled_table, metric_card,
)
from lifeline.auth.rbac import require_page
from lifeline.auth.roles import Role
from utils.sidebar import render_sidebar
from utils.database import (
    get_all_hospitals, get_contracts, add_contract, add_audit_log,
)
from dsa_engine import BLOOD_GROUPS

require_page(__file__)

inject_all_styles(get_theme())
render_sidebar()

_role = st.session_state.get("user_role", "")
_hosp_id = st.session_state.get("user_hospital_id")
_uid = int(st.session_state.get("user_id", 0))
_hosp_name = st.session_state.get("user_hospital_name", "")

# ── Title Block ──
st.markdown("""
<div style="margin-bottom:24px">
    <h1 style="font-family:'Syne',sans-serif;font-size:1.6rem;margin:0">Vendor Contracts</h1>
    <p style="color:var(--text-secondary);font-size:0.82rem;margin:4px 0 0">
        Manage blood supply contracts with vendors and partner organizations
    </p>
</div>""", unsafe_allow_html=True)

if _role == Role.SUPER_ADMIN:
    hospitals = get_all_hospitals()
    hosp_map = {h["name"]: h["id"] for h in hospitals}
    sel_name = st.selectbox("Hospital", list(hosp_map.keys()))
    sel_hosp_id = hosp_map[sel_name]
else:
    sel_hosp_id = _hosp_id
    sel_name = _hosp_name

tab1, tab2 = st.tabs(["Active Contracts", "New Contract"])

with tab1:
    contracts = get_contracts(sel_hosp_id if _role != Role.SUPER_ADMIN else None)
    if not contracts:
        alert_banner("No contracts found. Create a contract using the 'New Contract' tab.", "info")
    else:
        # Metrics
        active = [c for c in contracts if c.get("status") == "ACTIVE"]
        today = datetime.today()
        expiring_soon = []
        for c in active:
            if c.get("contract_end"):
                try:
                    end_dt = datetime.strptime(c["contract_end"][:10], "%Y-%m-%d")
                    if 0 <= (end_dt - today).days <= 30:
                        expiring_soon.append(c)
                except Exception:
                    pass

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(metric_card("Total Contracts", f"{len(contracts)}", icon="Contracts", variant="default"), unsafe_allow_html=True)
        with c2:
            st.markdown(metric_card("Active Contracts", f"{len(active)}", icon="Active", variant="success"), unsafe_allow_html=True)
        with c3:
            st.markdown(metric_card("Expiring Soon", f"{len(expiring_soon)}", icon="Expiring", variant="critical" if expiring_soon else "default"), unsafe_allow_html=True)

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        if expiring_soon:
            alert_banner(f"{len(expiring_soon)} contract(s) expiring within 30 days!", "warning")

        history_rows = []
        for c in contracts:
            history_rows.append({
                "Hospital": c.get("hospital_name", "—"),
                "Vendor": c.get("vendor_name", "—"),
                "Blood Group": blood_badge(c.get("blood_group", "?")),
                "Units/Month": f"{c.get('units_per_month', 0)}u",
                "Start": c.get("contract_start", "")[:10],
                "End": c.get("contract_end", "")[:10],
                "Status": status_pill(c.get("status", "PENDING"))
            })
        df_show = pd.DataFrame(history_rows)
        styled_table(df_show)

with tab2:
    if _role == Role.STAFF:
        alert_banner("Staff cannot create contracts. Contact your Hospital Admin.", "danger")
    else:
        section_header("New Vendor Contract")
        
        error_msg = None
        success_msg = None
        
        with st.form("contract_form"):
            col1, col2 = st.columns(2)
            with col1:
                vendor = st.text_input("Vendor / Supplier Name *", placeholder="e.g. Punjab Blood Service")
                blood_grp = st.selectbox("Blood Group", BLOOD_GROUPS)
                units_month = st.number_input("Units per Month", min_value=1, max_value=1000, value=50)
            with col2:
                start = st.date_input("Contract Start Date", value=datetime.today())
                end = st.date_input("Contract End Date", value=datetime.today() + timedelta(days=365))

            submitted = st.form_submit_button("Create Contract", use_container_width=True)
            if submitted:
                if not vendor:
                    error_msg = "Vendor name is required."
                elif start >= end:
                    error_msg = "End date must be after start date."
                else:
                    ok = add_contract(sel_hosp_id, vendor, blood_grp, units_month, str(start), str(end))
                    if ok:
                        add_audit_log("CONTRACT_CREATED", f"Contract with {vendor} for {blood_grp} at {sel_name}", _uid)
                        success_msg = f"Contract with {vendor} created successfully!"
                    else:
                        error_msg = "Failed to create contract."

        if success_msg:
            alert_banner(success_msg, "success")
            st.rerun()
        elif error_msg:
            alert_banner(error_msg, "danger")

