# pages/2_inventory.py
"""Blood Inventory Management — LIFELINE v6.0"""
from __future__ import annotations

import streamlit as st
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Inventory — LIFELINE", layout="wide")

from utils.styles import (
    inject_all_styles, get_theme, section_header, alert_banner,
    blood_badge, status_pill, styled_table, chart_template, chart_font,
)
from lifeline.auth.rbac import require_page
from lifeline.auth.roles import Role
from utils.sidebar import render_sidebar
from lifeline import clock
from lifeline.engine.sorting import fefo_sort
from lifeline.services.inventory import issue_units, receive_units
from utils.actions import attempt
from utils.database import get_all_hospitals, get_blood_units

user = require_page(__file__)

inject_all_styles(get_theme())
render_sidebar()

_role = st.session_state.get("user_role", "")
_hosp_id = st.session_state.get("user_hospital_id")
_uid = int(st.session_state.get("user_id", 0))
_hosp_name = st.session_state.get("user_hospital_name", "")

# ── Title Block ──
st.markdown("""
<div style="margin-bottom:24px">
    <h1 style="font-family:'Syne',sans-serif;font-size:1.6rem;margin:0">Inventory</h1>
    <p style="color:var(--text-secondary);font-size:0.82rem;margin:4px 0 0">
        Live stock and supply management
    </p>
</div>""", unsafe_allow_html=True)

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

# ── Hospital selection ──
if _role == Role.SUPER_ADMIN:
    hospitals = get_all_hospitals()
    hosp_map = {h["name"]: h["id"] for h in hospitals}
    sel_hosp_name = st.selectbox("Select Hospital", list(hosp_map.keys()))
    sel_hosp_id = hosp_map[sel_hosp_name]
else:
    sel_hosp_id = _hosp_id
    sel_hosp_name = _hosp_name
    alert_banner(f"Showing inventory for: {sel_hosp_name}", "info")

tab1, tab2, tab3 = st.tabs(["Current Stock", "Add Stock", "Consume Stock"])

# ── Tab 1: View ──
with tab1:
    units = get_blood_units(sel_hosp_id)
    if not units:
        alert_banner("No blood units recorded. Add stock using the 'Add Stock' tab.", "warning")
    else:
        # Summary chart
        summary = {}
        for u in units:
            bg = u["blood_group"]
            summary[bg] = summary.get(bg, 0) + u["units"]

        df_sum = pd.DataFrame(list(summary.items()), columns=["Blood Group", "Units"]).sort_values("Units", ascending=False)
        fig = px.bar(df_sum, x="Blood Group", y="Units",
                     color="Units", color_continuous_scale=["#1a0533", "#ff416c"],
                     template=chart_template(), title=f"Stock at {sel_hosp_name}")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font=chart_font(), plot_bgcolor="rgba(0,0,0,0)",
                          height=300, coloraxis_showscale=False, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True, theme=None)

        # First-Expired-First-Out order from the engine (units are already unexpired: expired ones are not stock)
        fefo = fefo_sort(units, clock.today(), soon_days=7)
        if fefo.expiring_soon:
            alert_banner(f"{sum(u['units'] for u in fefo.expiring_soon)} unit(s) expire within 7 days - use these first.", "danger")
            styled_table(pd.DataFrame([{
                "Blood Group": blood_badge(u["blood_group"]), "Units": u["units"], "Expiry Date": u["expiry_date"][:10],
                "Days Left": (datetime.strptime(u["expiry_date"][:10], "%Y-%m-%d").date() - clock.today()).days,
            } for u in fefo.expiring_soon]))

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        # Full inventory table
        section_header("Dispatch order (FEFO)", "Earliest expiry leaves first; stock is issued in this order")
        styled_table(pd.DataFrame([{
            "Blood Group": blood_badge(u["blood_group"]),
            "Units": u["units"],
            "Expiry Date": u["expiry_date"][:10],
            "Last Updated": u["updated_at"][:16].replace("T", " ") if u.get("updated_at") else "—",
        } for u in fefo.dispatch_order]))

# ── Tab 2: Add Stock ──
with tab2:
    section_header("Add New Blood Units")
    
    error_msg = None
    
    with st.form("add_stock_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            bg = st.selectbox("Blood Group", BLOOD_GROUPS, key="add_bg")
        with col2:
            qty = st.number_input("Units to Add", min_value=1, max_value=500, value=10)
        with col3:
            default_expiry = (datetime.now() + timedelta(days=21)).strftime("%Y-%m-%d")
            expiry = st.date_input("Expiry Date", value=datetime.strptime(default_expiry, "%Y-%m-%d"))

        submitted = st.form_submit_button("Add to Inventory", use_container_width=True)
        if submitted:
            ok, error_msg, _ = attempt(receive_units, user, sel_hosp_id, bg, int(qty), expiry)
            if ok:
                st.toast(f"Added {qty} unit(s) of {bg} to {sel_hosp_name}")
                st.rerun()

    if error_msg:
        alert_banner(error_msg, "danger")

# ── Tab 3: Consume Stock ──
with tab3:
    section_header("Record Stock Consumption")
    
    error_msg_c = None
    
    with st.form("consume_form"):
        col1, col2 = st.columns(2)
        with col1:
            bg_c = st.selectbox("Blood Group", BLOOD_GROUPS, key="con_bg")
        with col2:
            qty_c = st.number_input("Units Consumed", min_value=1, max_value=200, value=1)
        reason_c = st.text_input("Reason / Patient Reference", placeholder="e.g. Surgery – Ward 3")
        submitted_c = st.form_submit_button("Record Consumption", use_container_width=True)
        if submitted_c:
            ok, error_msg_c, _ = attempt(issue_units, user, sel_hosp_id, bg_c, int(qty_c), reason_c)
            if ok:
                st.toast(f"Recorded consumption of {qty_c} unit(s) of {bg_c}")
                st.rerun()

    if error_msg_c:
        alert_banner(error_msg_c, "danger")
