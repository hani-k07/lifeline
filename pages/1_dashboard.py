"""Dashboard: the whole network state on one screen."""
from __future__ import annotations

from collections import Counter

import streamlit as st

from lifeline import clock
from lifeline.auth.roles import Role
from lifeline.engine.forecasting import wma_forecast
from lifeline.engine.triage import triage_order
from lifeline.ui import charts
from lifeline.ui import components as ui
from lifeline.ui.layout import guard, page
from utils.database import (
    get_all_hospitals,
    get_blood_requests,
    get_contracts,
    get_daily_usage,
    get_dashboard_stats,
    get_expiring_units,
)
from utils.helpers import time_until

user = page(__file__, "Dashboard", "Live stock, emergencies and loans across the network")

with guard():
    scope = None if user.role is Role.SUPER_ADMIN else user.hospital_id
    if user.role is Role.SUPER_ADMIN:
        hospitals = get_all_hospitals()
        choice = st.selectbox("Hospital", ["All hospitals"] + [h["name"] for h in hospitals], key="dash_scope",
                              label_visibility="collapsed")
        scope = next((h["id"] for h in hospitals if h["name"] == choice), None)

    stats = get_dashboard_stats(scope)
    requests = [r for r in get_blood_requests(scope) if r["status"] in ("PENDING", "RESERVED")]
    loans = get_contracts(scope)
    overdue = [c for c in loans if c["status"] == "BREACHED"]
    critical_requests = sum(1 for r in requests if r["urgency"] == "CRITICAL")

    ui.kpi_row(
        ui.kpi_card("Units available", stats["total_units"], hint="unexpired, in stock"),
        ui.kpi_card("Groups in critical stock", len(stats["critical_groups"]),
                    hint=", ".join(stats["critical_groups"]) or "none", tone="danger" if stats["critical_groups"] else "success"),
        ui.kpi_card("Open emergencies", len(requests), hint=f"{critical_requests} critical", tone="danger" if critical_requests else "neutral"),
        ui.kpi_card("Overdue loans", len(overdue), hint="past their return deadline", tone="danger" if overdue else "success"),
    )

    left, right = st.columns([2, 1], gap="medium")
    with left:
        ui.section_header("Stock by blood group", "available, unexpired units")
        ui.render(ui.stock_grid(stats["blood_summary"]))

        history = get_daily_usage(scope, None, 14)
        forecast = wma_forecast(history, horizon=7)
        ui.section_header("Demand", "units issued or transfused per day, with a 7-day forecast")
        charts.show(charts.usage_forecast(history, forecast, "", height=200))

    with right:
        ui.section_header("Expiring in 72 hours", "use these first")
        soon = Counter((u["hospital_name"], u["blood_group"], u["expiry_date"][:10]) for u in get_expiring_units(scope, 3))
        ui.render(ui.row_list([(ui.Html(f"{n} × {ui.blood_group_badge(group)}"), f"{hospital} · {expiry}")
                               for (hospital, group, expiry), n in sorted(soon.items(), key=lambda kv: kv[0][2])[:4]],
                              empty="Nothing expires in the next 72 hours"))

        ui.section_header("Open emergencies")
        ui.render(ui.row_list([(ui.Html(f"{ui.status_pill(r['urgency'])} {ui.blood_group_badge(r['blood_group'])} × {r['units_needed']}"),
                                f"#{r['id']} · {r['status'].title()}") for r in triage_order(requests)[:3]],
                              empty="No open emergencies"))

        ui.section_header("Loans due")
        due = sorted((c for c in loans if c["status"] in ("ACTIVE", "BREACHED")), key=lambda c: c["return_deadline"])[:2]
        ui.render(ui.row_list([(ui.Html(f"{ui.status_pill(c['status'])} {c['units']} × {ui.blood_group_badge(c['blood_group'])}"),
                                f"{c['borrower_name']} · {time_until(c['return_deadline'])}") for c in due], empty="No loans outstanding"))
    st.caption(f"Updated {clock.now().strftime('%d %b %Y, %H:%M')} PKT")
