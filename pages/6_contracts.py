# pages/6_contracts.py
"""Blood Loans (lend / borrow contracts) — LIFELINE v6.0"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Contracts — LIFELINE", layout="wide")

from lifeline.constants import BLOOD_GROUPS
from lifeline.engine.sorting import merge_sort
from lifeline import clock
from lifeline.auth.rbac import require_page
from lifeline.auth.roles import Role
from lifeline.services.contracts import create_loan, return_loan
from utils.actions import attempt
from utils.database import get_all_hospitals, get_contracts
from utils.helpers import time_until
from utils.sidebar import render_sidebar
from utils.styles import (
    alert_banner,
    blood_badge,
    get_theme,
    inject_all_styles,
    metric_card,
    section_header,
    status_pill,
    styled_table,
)

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
    <h1 style="font-family:'Syne',sans-serif;font-size:1.6rem;margin:0">Blood Loans</h1>
    <p style="color:var(--text-secondary);font-size:0.82rem;margin:4px 0 0">
        Units lent between hospitals, with a return deadline. Overdue loans are flagged automatically.
    </p>
</div>""", unsafe_allow_html=True)

hospitals = get_all_hospitals()
names = {h["id"]: h["name"] for h in hospitals}
tab1, tab2 = st.tabs(["Loans", "New Loan"])

with tab1:
    contracts = merge_sort(get_contracts(None if _role == Role.SUPER_ADMIN else _hosp_id), key=lambda c: c["return_deadline"])
    if not contracts:
        alert_banner("No loans yet. Create one in the 'New Loan' tab.", "info")
    else:
        active = [c for c in contracts if c["status"] == "ACTIVE"]
        breached = [c for c in contracts if c["status"] == "BREACHED"]
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(metric_card("Total Loans", f"{len(contracts)}", icon="Loans", variant="default"), unsafe_allow_html=True)
        with c2:
            st.markdown(metric_card("Active", f"{len(active)}", icon="Active", variant="success"), unsafe_allow_html=True)
        with c3:
            st.markdown(metric_card("Overdue", f"{len(breached)}", icon="Breached",
                                    variant="critical" if breached else "default"), unsafe_allow_html=True)
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if breached:
            alert_banner(f"{len(breached)} loan(s) are past their return deadline.", "danger")

        styled_table(pd.DataFrame([{
            "Ticket": c["ticket_id"],
            "Lender": c["lender_name"],
            "Borrower": c["borrower_name"],
            "Blood Group": blood_badge(c["blood_group"]),
            "Units": f"{c['units']}u",
            "Deadline": c["return_deadline"][:16].replace("T", " "),
            "Time left": time_until(c["return_deadline"]) if c["status"] in ("ACTIVE", "BREACHED") else "—",
            "Status": status_pill(c["status"]),
        } for c in contracts]))

        open_loans = [c for c in contracts if c["status"] in ("ACTIVE", "BREACHED")]
        if open_loans:
            section_header("Settle a loan", "The borrower hands the same number of units of the same group back")
            settle_error = None
            for c in open_loans:
                col_a, col_b = st.columns([4, 1])
                col_a.markdown(f"{c['ticket_id']} · {c['units']}u {c['blood_group']} · {c['borrower_name']} → {c['lender_name']}"
                               f" {status_pill(c['status'])}", unsafe_allow_html=True)
                if col_b.button("Mark returned", key=f"ret_{c['id']}"):
                    ok, settle_error, _ = attempt(return_loan, user, c["id"])
                    if ok:
                        st.toast(f"Loan {c['ticket_id']} settled")
                        st.rerun()
            if settle_error:
                alert_banner(settle_error, "danger")

with tab2:
    if _role == Role.STAFF:
        alert_banner("Staff cannot create loans. Contact your Hospital Admin.", "danger")
    else:
        section_header("Lend blood to another hospital")
        loan_error = None
        with st.form("loan_form"):
            col1, col2 = st.columns(2)
            with col1:
                if _role == Role.SUPER_ADMIN:
                    lender_id = next(h["id"] for h in hospitals if h["name"] == st.selectbox("Lending hospital", list(names.values())))
                else:
                    lender_id = _hosp_id
                    st.text_input("Lending hospital", value=_hosp_name, disabled=True)
                borrowers = {h["name"]: h["id"] for h in hospitals if h["id"] != lender_id}
                borrower_id = borrowers[st.selectbox("Borrowing hospital", list(borrowers.keys()))]
                blood_grp = st.selectbox("Blood Group", BLOOD_GROUPS)
            with col2:
                units = st.number_input("Units", min_value=1, max_value=100, value=2)
                hours = st.number_input("Return within (hours)", min_value=1, max_value=24 * 30, value=72)
            if st.form_submit_button("Create Loan", use_container_width=True):
                ok, loan_error, _ = attempt(create_loan, user, lender_id, borrower_id, blood_grp, int(units),
                                            clock.now() + timedelta(hours=int(hours)))
                if ok:
                    st.toast(f"{units} unit(s) of {blood_grp} lent to {names[borrower_id]}")
                    st.rerun()
        if loan_error:
            alert_banner(loan_error, "danger")
