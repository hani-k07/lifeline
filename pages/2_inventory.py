"""Inventory: stock at a glance, first-expired-first-out order, receiving and issuing."""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from lifeline import clock
from lifeline.auth.roles import Role
from lifeline.constants import BLOOD_GROUPS, MAX_UNITS_PER_RECEIPT
from lifeline.engine.sorting import fefo_sort
from lifeline.services.inventory import MAX_SHELF_LIFE_DAYS, discard_unit, issue_units, receive_units
from lifeline.ui import charts
from lifeline.ui import components as ui
from lifeline.ui.layout import guard, page
from utils.actions import attempt
from utils.database import get_all_hospitals, get_blood_summary, get_blood_units, get_unit_by_code

user = page(__file__, "Inventory", "Stock, first-expired-first-out order, receiving and issuing")

with guard():
    if user.role is Role.SUPER_ADMIN:
        hospitals = get_all_hospitals()
        names = {h["name"]: h["id"] for h in hospitals}
        hospital_name = st.selectbox("Hospital", list(names), key="inv_hosp")
        hospital_id = names[hospital_name]
    else:
        hospital_id, hospital_name = user.hospital_id, user.hospital_name
    assert hospital_id is not None

    today = clock.today()
    tab_stock, tab_receive, tab_issue = st.tabs(["Stock", "Receive stock", "Issue or discard"])

    with tab_stock:
        counts = get_blood_summary(hospital_id)
        ui.render(ui.stock_grid(counts))
        units = get_blood_units(hospital_id)
        fefo = fefo_sort(units, today, soon_days=3)
        if fefo.expiring_soon:
            n = sum(u["units"] for u in fefo.expiring_soon)
            ui.alert_banner(f"{n} unit(s) expire within 3 days. They are first in the dispatch order below.", "warning", title="Use first")
        ui.section_header("Dispatch order (FEFO)", "earliest expiry leaves first")
        rows = [{**u, "days_left": (date.fromisoformat(u["expiry_date"][:10]) - today).days} for u in fefo.dispatch_order]
        ui.data_table(
            rows,
            [ui.Col("Blood group", "blood_group", render=lambda v, r: ui.blood_group_badge(v)),
             ui.Col("Units", "units", align="right"), ui.Col("Expires", "expiry_date", render=lambda v, r: str(v)[:10]),
             ui.Col("Days left", "days_left", align="right"),
             ui.Col("", "days_left", render=lambda v, r: ui.status_pill("use first", kind="warning") if v <= 3 else "", sortable=False, search=False)],
            key="inv_fefo", empty_title="No stock recorded", empty_body="Receive units in the 'Receive stock' tab.")
        charts.show(charts.stock_bars(counts))

    with tab_receive:
        ui.section_header("Receive units", f"into {hospital_name}")
        c1, c2 = st.columns(2)
        group = c1.selectbox("Blood group", BLOOD_GROUPS, key="rcv_group")
        count = c2.number_input("Number of units", min_value=1, max_value=MAX_UNITS_PER_RECEIPT, value=10, step=1, key="rcv_units")
        c3, c4 = st.columns(2)
        collected = c3.date_input("Collection date", value=today, max_value=today, key="rcv_collected")
        expiry = c4.date_input("Expiry date", value=today + timedelta(days=35), key="rcv_expiry",
                               help="Red-cell units usually last 35 days from collection.")
        problem = None
        if expiry <= today:
            problem = "The expiry date must be in the future: expired units cannot be added to stock."
        elif expiry < collected:
            problem = "The expiry date is before the collection date."
        elif (expiry - collected).days > MAX_SHELF_LIFE_DAYS:
            problem = f"That is more than {MAX_SHELF_LIFE_DAYS} days after collection. Please check the date."
        ui.field_error(problem)
        if st.button("Add to stock", type="primary", key="rcv_go", disabled=problem is not None):
            ok, error, _ = attempt(receive_units, user, hospital_id, group, int(count), expiry, collected_at=collected)
            if ok:
                st.toast(f"Added {count} unit(s) of {group} to {hospital_name}")
                st.rerun()
            ui.alert_banner(error or "Could not add the units.", "danger")

    with tab_issue:
        ui.section_header("Issue units", "removes units from stock, earliest expiry first")
        c1, c2 = st.columns(2)
        group_i = c1.selectbox("Blood group", BLOOD_GROUPS, key="iss_group")
        available = counts.get(group_i, 0)
        count_i = c2.number_input("Number of units", min_value=1, max_value=MAX_UNITS_PER_RECEIPT, value=1, step=1, key="iss_units")
        reason = st.text_input("Reason or patient reference", key="iss_reason", placeholder="e.g. Surgery, Ward 3")
        st.caption(f"In stock: {available} unit(s) of {group_i}")
        short = int(count_i) > available
        ui.field_error(f"Only {available} unit(s) of {group_i} are in stock." if short else None)
        if ui.confirm_dialog("issue", "Issue units", f"Issue {int(count_i)} × {group_i} from {hospital_name}? This cannot be undone.",
                             confirm_label="Yes, issue", disabled=short):
            ok, error, codes = attempt(issue_units, user, hospital_id, group_i, int(count_i), reason)
            if ok:
                st.toast(f"Issued {len(codes)} unit(s): {', '.join(codes[:4])}{'…' if len(codes) > 4 else ''}")
                st.rerun()
            ui.alert_banner(error or "Could not issue the units.", "danger")

        ui.section_header("Discard a unit", "damaged, cold-chain break, contaminated")
        code = st.text_input("Unit code", key="dsc_code", placeholder="e.g. U0000123")
        why = st.text_input("Reason (required)", key="dsc_reason")
        unit = get_unit_by_code(code.strip()) if code.strip() else None
        problem = "No unit has that code." if code.strip() and unit is None else None
        if unit and user.role is not Role.SUPER_ADMIN and unit["hospital_id"] != hospital_id:
            unit, problem = None, "That unit belongs to another hospital."
        ui.field_error(problem)
        if ui.confirm_dialog("discard", "Discard unit", f"Discard unit {code.strip()}? It will be written off permanently.",
                             confirm_label="Yes, discard", danger=True, disabled=unit is None or not why.strip()) and unit:
            ok, error, _ = attempt(discard_unit, user, unit["id"], why)
            if ok:
                st.toast(f"Unit {code.strip()} discarded")
                st.rerun()
            ui.alert_banner(error or "Could not discard the unit.", "danger")
