"""Loans: units lent between hospitals with a return deadline; overdue loans are flagged automatically."""
from __future__ import annotations

from datetime import timedelta

import streamlit as st

from lifeline import clock
from lifeline.auth.roles import Role
from lifeline.constants import BLOOD_GROUPS
from lifeline.engine.sorting import merge_sort
from lifeline.services.contracts import create_loan, return_loan
from lifeline.ui import components as ui
from lifeline.ui.layout import guard, page
from utils.actions import attempt
from utils.database import get_all_hospitals, get_contracts
from utils.helpers import time_until

user = page(__file__, "Loans", "Blood lent between hospitals, with a return deadline")

with guard():
    hospitals = get_all_hospitals()
    names = {h["id"]: h["name"] for h in hospitals}
    tab_loans, tab_new = st.tabs(["Loans", "New loan"])

    with tab_loans:
        contracts = merge_sort(get_contracts(None if user.role is Role.SUPER_ADMIN else user.hospital_id), key=lambda c: c["return_deadline"])
        active = [c for c in contracts if c["status"] == "ACTIVE"]
        overdue = [c for c in contracts if c["status"] == "BREACHED"]
        ui.kpi_row(ui.kpi_card("Loans", len(contracts)), ui.kpi_card("Active", len(active), tone="success"),
                   ui.kpi_card("Overdue", len(overdue), tone="danger" if overdue else "neutral"))
        if overdue:
            ui.alert_banner(f"{len(overdue)} loan(s) are past their return deadline.", "danger", title="Overdue")
        ui.data_table(
            contracts,
            [ui.Col("Ticket", "ticket_id"), ui.Col("Lender", "lender_name"), ui.Col("Borrower", "borrower_name"),
             ui.Col("Group", "blood_group", render=lambda v, r: ui.blood_group_badge(v)), ui.Col("Units", "units", align="right"),
             ui.Col("Deadline", "return_deadline", render=lambda v, r: str(v)[:16].replace("T", " ")),
             ui.Col("Time left", "return_deadline", render=lambda v, r: time_until(v) if r["status"] in ("ACTIVE", "BREACHED") else "—",
                    sortable=False, search=False),
             ui.Col("Status", "status", render=lambda v, r: ui.status_pill(v))],
            key="loan_tbl", empty_title="No loans yet", empty_body="Create one in the 'New loan' tab.")
        open_loans = [c for c in contracts if c["status"] in ("ACTIVE", "BREACHED")]
        if open_loans:
            ui.section_header("Settle a loan", "the borrower hands the same number of units of the same group back")
            error = None
            for c in open_loans:
                left, right = st.columns([4, 2])
                left.markdown(f"{ui.esc(c['ticket_id'])} · {c['units']} × {ui.blood_group_badge(c['blood_group'])} · "
                              f"{ui.esc(c['borrower_name'])} → {ui.esc(c['lender_name'])} {ui.status_pill(c['status'])}", unsafe_allow_html=True)
                with right:
                    if ui.confirm_dialog(f"ret_{c['id']}", "Mark returned",
                                         f"Return {c['units']} × {c['blood_group']} from {c['borrower_name']} to {c['lender_name']}?",
                                         confirm_label="Yes, returned"):
                        ok, error, _ = attempt(return_loan, user, c["id"])
                        if ok:
                            st.toast(f"Loan {c['ticket_id']} settled")
                            st.rerun()
            if error:
                ui.alert_banner(error, "danger")

    with tab_new:
        if user.role is Role.STAFF:
            ui.alert_banner("Staff cannot create loans. Ask your hospital administrator.", "warning", title="Not allowed")
        else:
            ui.section_header("Lend blood to another hospital")
            if user.role is Role.SUPER_ADMIN:
                by_name = {v: k for k, v in names.items()}
                lender_id = by_name[st.selectbox("Lending hospital", list(by_name), key="loan_lender")]
            else:
                lender_id = user.hospital_id
                st.text_input("Lending hospital", value=user.hospital_name, disabled=True)
            borrowers = {v: k for k, v in names.items() if k != lender_id}
            c1, c2, c3 = st.columns(3)
            borrower_id = borrowers[c1.selectbox("Borrowing hospital", list(borrowers), key="loan_borrower")]
            group = c2.selectbox("Blood group", BLOOD_GROUPS, key="loan_group")
            units = c3.number_input("Units", min_value=1, max_value=100, value=2, step=1, key="loan_units")
            hours = st.number_input("Return within (hours)", min_value=1, max_value=24 * 30, value=72, step=1, key="loan_hours")
            if ui.confirm_dialog("loan_new", "Create loan", f"Lend {int(units)} × {group} to {names[borrower_id]}? The units move now.",
                                 confirm_label="Yes, lend"):
                ok, error, _ = attempt(create_loan, user, lender_id, borrower_id, group, int(units), clock.now() + timedelta(hours=int(hours)))
                if ok:
                    st.toast(f"{int(units)} unit(s) of {group} lent to {names[borrower_id]}")
                    st.rerun()
                ui.alert_banner(error or "Could not create the loan.", "danger")
