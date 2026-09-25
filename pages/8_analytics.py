# pages/8_analytics.py
"""Analytics & Reporting — LIFELINE v6.0"""
from __future__ import annotations

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Analytics — LIFELINE", layout="wide")

from utils.styles import (
    inject_all_styles, get_theme, section_header, alert_banner,
    blood_badge, status_pill, styled_table, metric_card, chart_template, chart_font,
)
from lifeline.auth.rbac import require_page
from lifeline.auth.roles import Role
from utils.sidebar import render_sidebar
from utils.database import (
    get_all_hospitals, get_blood_units, get_donors,
    get_transfusions, get_blood_requests, get_blood_summary, get_daily_usage,
)
from lifeline import clock
from lifeline.constants import BLOOD_GROUPS
from lifeline.engine.clustering import segment_donors
from lifeline.engine.forecasting import predict_shortage, shortage_risk, wma_forecast
from utils.network import get_road_graph

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
    <h1 style="font-family:'Syne',sans-serif;font-size:1.6rem;margin:0">Analytics & Intelligence</h1>
    <p style="color:var(--text-secondary);font-size:0.82rem;margin:4px 0 0">
        Demand forecasting, shortage prediction, and network analysis
    </p>
</div>""", unsafe_allow_html=True)

if _role == Role.SUPER_ADMIN:
    hospitals = get_all_hospitals()
    hosp_map = {"All Hospitals": None}
    for h in hospitals:
        hosp_map[h["name"]] = h["id"]
    sel_name = st.selectbox("Hospital", list(hosp_map.keys()))
    sel_hosp_id = hosp_map[sel_name]
else:
    sel_hosp_id = _hosp_id
    sel_name = _hosp_name

tab1, tab2, tab_donors, tab3 = st.tabs(["Inventory Overview", "Demand Forecast", "Donors", "Network Map"])

with tab1:
    units = get_blood_units(sel_hosp_id)
    donors = get_donors(sel_hosp_id)
    transfusions = get_transfusions(sel_hosp_id)

    total_u = sum(u["units"] for u in units)
    group_types = len(set(u["blood_group"] for u in units))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(metric_card("Total Blood Units", f"{total_u}", icon="Units", variant="default"), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("Blood Group Types", f"{group_types}", icon="Types", variant="default"), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Registered Donors", f"{len(donors)}", icon="Donors", variant="success"), unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card("Transfusions", f"{len(transfusions)}", icon="Transfusions", variant="default"), unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    if units:
        # By blood group
        summary = {}
        for u in units:
            bg = u["blood_group"]
            summary[bg] = summary.get(bg, 0) + u["units"]

        df_bg = pd.DataFrame(list(summary.items()), columns=["Blood Group", "Units"]).sort_values("Units", ascending=False)
        fig1 = px.bar(df_bg, x="Blood Group", y="Units", color="Units",
                      color_continuous_scale=["#1a0533", "#ff416c"],
                      template=chart_template(), title="Stock by Blood Group")
        fig1.update_layout(paper_bgcolor="rgba(0,0,0,0)", font=chart_font(), plot_bgcolor="rgba(0,0,0,0)",
                           coloraxis_showscale=False, height=320, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig1, use_container_width=True, theme=None)

        # Donut chart
        fig2 = px.pie(df_bg, values="Units", names="Blood Group", hole=0.5,
                      template=chart_template(), title="Distribution")
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", font=chart_font(), height=320, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig2, use_container_width=True, theme=None)
    else:
        alert_banner("No inventory data to display.", "info")

with tab2:
    section_header("7-Day Demand Forecast", "Weighted moving average of real usage (units issued or transfused per day)")

    fg_bg = st.selectbox("Blood Group", BLOOD_GROUPS, key="fg_bg")
    historical = get_daily_usage(sel_hosp_id, fg_bg, 14)
    if not any(historical):
        alert_banner("No usage recorded for this group in the last 14 days; the forecast below is flat.", "info")
    current_stock = get_blood_summary(sel_hosp_id).get(fg_bg, 0)

    forecast = wma_forecast(historical, horizon=7, window=7)
    risk = shortage_risk(current_stock, forecast)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(metric_card("Current Stock", f"{current_stock} u", icon="Stock", variant="default"), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("7-Day Avg Forecast", f"{sum(forecast) / 7:.1f} u/day", icon="Forecast", variant="default"), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Risk Level", risk.risk_level, icon="Risk",
                                variant="critical" if risk.risk_level in ("CRITICAL", "HIGH") else "success"), unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    days_hist = [f"Day -{14 - i}" for i in range(14)]
    days_fore = [f"Day +{i + 1}" for i in range(7)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=days_hist, y=historical, name="Historical", line=dict(color="#64b5f6", width=2)))
    fig.add_trace(go.Scatter(x=days_fore, y=forecast, name="Forecast (WMA)", line=dict(color="#ff416c", width=2, dash="dash")))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font=chart_font(), plot_bgcolor="rgba(0,0,0,0)",
                      template=chart_template(), height=350, title=f"Usage Forecast — {fg_bg} at {sel_name}",
                      xaxis=dict(showgrid=False, title="Day"),
                      yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="Units per day"))
    st.plotly_chart(fig, use_container_width=True, theme=None)

    if risk.risk_level in ("CRITICAL", "HIGH"):
        alert_banner(f"Reorder {risk.recommended_reorder} units of {fg_bg} — stock-out expected in {risk.days_until_stockout} day(s).", "danger")
    elif risk.risk_level == "MEDIUM":
        alert_banner(f"Monitor stock — consider ordering {risk.recommended_reorder} additional units.", "warning")
    else:
        alert_banner("Stock covers the forecast horizon." if risk.days_until_stockout is None else "Stock level is adequate.", "success")

    section_header("All blood groups", "Shortage outlook for the next 7 days")
    summary = get_blood_summary(sel_hosp_id)
    rows = predict_shortage([{"blood_group": g, "stock": summary.get(g, 0), "history": get_daily_usage(sel_hosp_id, g, 14)}
                             for g in BLOOD_GROUPS])
    styled_table(pd.DataFrame([{
        "Blood Group": blood_badge(r["blood_group"]), "Stock": r["stock"], "Avg use / day": r["avg_daily_demand"],
        "Trend": r["trend"], "Days to stock-out": "beyond 7" if r["days_until_stockout"] is None else r["days_until_stockout"],
        "Risk": status_pill(r["risk_level"]), "Suggested reorder": r["recommended_reorder"],
    } for r in rows]))

with tab_donors:
    section_header("Donor segments", "K-Means on age, number of donations and time since last donation")
    donor_rows = get_donors(sel_hosp_id)
    if len(donor_rows) < 3:
        alert_banner("At least 3 registered donors are needed to segment them.", "info")
    else:
        seg = segment_donors(donor_rows, clock.today())
        cols = st.columns(len(seg["summary"]))
        for col, item in zip(cols, seg["summary"], strict=True):
            with col:
                st.markdown(metric_card(item["segment"].title(), f"{item['count']}", icon="Donors",
                                        delta=f"avg {item['avg_donations']} donations, last {item['avg_days_since_last']} d ago",
                                        variant="critical" if item["segment"] == "LAPSED" else "default"), unsafe_allow_html=True)
        st.caption("LAPSED donors have gone longest without donating: contact them first.")
        lapsed = [x for x in seg["segments"] if x["segment"] == "LAPSED"]
        if lapsed:
            styled_table(pd.DataFrame([{"Donor": x["donor_name"], "Segment": status_pill(x["segment"])} for x in lapsed]))

with tab3:
    section_header("Hospital Network Map", "Sparse road network: each hospital linked to its 3 nearest, distances x 1.3 for roads")
    hospitals = get_all_hospitals()

    if hospitals:
        graph = get_road_graph(hospitals)
        df_h = pd.DataFrame(hospitals)
        df_h["stock"] = df_h["id"].map({h["id"]: sum(get_blood_summary(h["id"]).values()) for h in hospitals})
        df_h["size"] = df_h["stock"].apply(lambda n: max(10, min(40, n / 10)))

        fig_map = px.scatter_map(
            df_h, lat="latitude", lon="longitude", hover_name="name", hover_data={"stock": True, "phone": True},
            size="size", color="stock", color_continuous_scale=["#ff4444", "#ffaa00", "#00c853"],
            map_style="carto-darkmatter" if get_theme() == "dark" else "carto-positron",
            zoom=11, center={"lat": 31.52, "lon": 74.34}, title="Lahore Hospital Blood Network", template=chart_template(),
        )
        for a_id, b_id, km in graph.edges():
            na, nb = graph.nodes[a_id], graph.nodes[b_id]
            fig_map.add_trace(go.Scattermap(lat=[na.lat, nb.lat], lon=[na.lon, nb.lon], mode="lines",
                                            line=dict(width=1.5, color="#8892AA"), hoverinfo="text",
                                            text=f"{na.name} - {nb.name}: {km:.1f} km", showlegend=False))
        fig_map.update_layout(paper_bgcolor="rgba(0,0,0,0)", font=chart_font(), height=500, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_map, use_container_width=True, theme=None)

        with st.expander("Road distance matrix (km, shortest route through the network)"):
            ids = [h["id"] for h in hospitals]
            matrix = []
            for hid in ids:
                dists, _ = graph.dijkstra(hid)
                matrix.append({graph.nodes[t].name: round(dists.get(t, 0), 1) for t in ids})
            styled_table(pd.DataFrame(matrix, index=[h["name"] for h in hospitals]))
    else:
        alert_banner("No hospitals in the network.", "info")
