"""Analytics: stock, demand forecast, donor segments and the hospital network."""
from __future__ import annotations

import streamlit as st

from lifeline import clock
from lifeline.auth.roles import Role
from lifeline.constants import BLOOD_GROUPS
from lifeline.engine.clustering import segment_donors
from lifeline.engine.forecasting import predict_shortage, shortage_risk, wma_forecast
from lifeline.ui import charts
from lifeline.ui import components as ui
from lifeline.ui.layout import guard, page
from utils.database import (
    get_all_hospitals,
    get_blood_summary,
    get_daily_usage,
    get_donors,
    get_transfusions,
)
from utils.network import get_road_graph

user = page(__file__, "Analytics", "Demand forecast, shortage outlook, donor segments and the road network")

RISK_TONE = {"CRITICAL": "danger", "HIGH": "danger", "MEDIUM": "warning", "LOW": "success"}

with guard():
    hospitals = get_all_hospitals()
    if user.role is Role.SUPER_ADMIN:
        by_name = {"All hospitals": None, **{h["name"]: h["id"] for h in hospitals}}
        scope_name = st.selectbox("Hospital", list(by_name), key="an_scope")
        scope = by_name[scope_name]
    else:
        scope, scope_name = user.hospital_id, user.hospital_name

    tab_stock, tab_forecast, tab_donors, tab_network = st.tabs(["Stock", "Demand forecast", "Donors", "Network"])

    with tab_stock:
        counts = get_blood_summary(scope)
        donors = get_donors(scope)
        ui.kpi_row(ui.kpi_card("Units available", sum(counts.values())),
                   ui.kpi_card("Groups in stock", sum(1 for g in BLOOD_GROUPS if counts.get(g, 0) > 0), hint=f"of {len(BLOOD_GROUPS)}"),
                   ui.kpi_card("Registered donors", len(donors)),
                   ui.kpi_card("Transfusions", len(get_transfusions(scope))))
        if sum(counts.values()):
            charts.show(charts.stock_bars(counts))
        else:
            ui.empty_state("No stock to chart", "Receive units on the Inventory page.", icon="○")

    with tab_forecast:
        group = st.selectbox("Blood group", BLOOD_GROUPS, key="an_group")
        history = get_daily_usage(scope, group, 14)
        stock = counts.get(group, 0)
        forecast = wma_forecast(history, horizon=7, window=7)
        risk = shortage_risk(stock, forecast)
        ui.kpi_row(ui.kpi_card("In stock", f"{stock} units", hint=group),
                   ui.kpi_card("Forecast use", f"{sum(forecast) / 7:.1f} / day", hint="weighted moving average, next 7 days"),
                   ui.kpi_card("Risk", risk.risk_level, tone=RISK_TONE.get(risk.risk_level, "neutral"),
                               hint="stock-out beyond 7 days" if risk.days_until_stockout is None else f"stock-out in {risk.days_until_stockout} day(s)"))
        if not any(history):
            ui.alert_banner("No usage was recorded for this group in the last 14 days, so the forecast is flat.", "info")
        charts.show(charts.usage_forecast(history, forecast, f"{group} usage at {scope_name}"))
        if risk.risk_level in ("CRITICAL", "HIGH"):
            ui.alert_banner(f"Reorder {risk.recommended_reorder} units of {group}. Stock-out is expected in {risk.days_until_stockout} day(s).",
                            "danger", title="Act now")
        elif risk.risk_level == "MEDIUM":
            ui.alert_banner(f"Consider ordering {risk.recommended_reorder} more units of {group}.", "warning", title="Watch")
        else:
            ui.alert_banner("Stock covers the forecast horizon.", "success", title="Adequate")

        ui.section_header("Shortage outlook", "all blood groups, next 7 days")
        rows = predict_shortage([{"blood_group": g, "stock": counts.get(g, 0), "history": get_daily_usage(scope, g, 14)} for g in BLOOD_GROUPS])
        ui.data_table(
            rows,
            [ui.Col("Group", "blood_group", render=lambda v, r: ui.blood_group_badge(v)), ui.Col("Stock", "stock", align="right"),
             ui.Col("Use / day", "avg_daily_demand", align="right"), ui.Col("Trend", "trend"),
             ui.Col("Days to stock-out", "days_until_stockout", align="right",
                    render=lambda v, r: "beyond 7" if v is None else str(v)),
             ui.Col("Risk", "risk_level", render=lambda v, r: ui.status_pill(v)),
             ui.Col("Suggested reorder", "recommended_reorder", align="right")],
            key="an_short", page_size=8)

    with tab_donors:
        ui.section_header("Donor segments", "K-Means on age, number of donations and time since the last one")
        if len(donors) < 3:
            ui.empty_state("Not enough donors", "At least 3 registered donors are needed to segment them.", icon="○")
        else:
            seg = segment_donors(donors, clock.today())
            ui.kpi_row(*(ui.kpi_card(item["segment"].title(), item["count"], tone="danger" if item["segment"] == "LAPSED" else "neutral",
                                     hint=f"avg {item['avg_donations']} donations, last {item['avg_days_since_last']} d ago")
                         for item in seg["summary"]))
            lapsed = [x for x in seg["segments"] if x["segment"] == "LAPSED"]
            if lapsed:
                ui.alert_banner("Lapsed donors have gone longest without donating. Contact them first.", "info", title="Outreach")
                ui.data_table(lapsed, [ui.Col("Donor", "donor_name"), ui.Col("Segment", "segment", render=lambda v, r: ui.status_pill(v))],
                              key="an_lapsed", page_size=8)

    with tab_network:
        ui.section_header("Hospital network", "each hospital is linked to its 3 nearest; road distance is straight-line x 1.3")
        if not hospitals:
            ui.empty_state("No hospitals", "Add hospitals in the admin console.", icon="○")
        else:
            graph = get_road_graph(hospitals)
            edges = [(graph.nodes[a].lat, graph.nodes[a].lon, graph.nodes[b].lat, graph.nodes[b].lon) for a, b, _ in graph.edges()]
            charts.show(charts.route_map(hospitals, edges, height=420))
            st.caption("Marker colour and the hover text give each hospital's stock status: ok, low or critical.")
            with st.expander("Road distance matrix (km, shortest route through the network)"):
                names = {h["id"]: h["name"] for h in hospitals}
                matrix = []
                for hid in names:
                    dist, _ = graph.dijkstra(hid)
                    matrix.append({"from": names[hid], **{names[t]: round(dist.get(t, 0), 1) for t in names}})
                ui.render(ui.html_table(matrix, [ui.Col("From", "from"), *(ui.Col(n, n, align="right") for n in names.values())]))
