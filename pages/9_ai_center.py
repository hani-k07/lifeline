# pages/9_ai_center.py
"""AI Intelligence Hub — LIFELINE v6.0"""
from __future__ import annotations

import streamlit as st
import random
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="AI Center — LIFELINE", layout="wide")

from utils.styles import (
    inject_all_styles, get_theme, section_header, alert_banner,
    blood_badge, status_pill, styled_table, metric_card, render_ai_response,
)
from lifeline.auth.rbac import require_page
from utils.sidebar import render_sidebar
from utils.database import (
    get_all_hospitals, get_blood_units, get_blood_requests,
    get_transfusions, get_audit_logs, get_inventory_changes, log_ai_usage,
)
from ai_engine import (
    ai_demand_forecast, ai_emergency_triage,
    ai_chatbot, ai_anomaly_detection, ai_exchange_advisor,
)
from dsa_engine import build_hospital_graph, forecast_demand, detect_shortage_risk, BLOOD_GROUPS

require_page(__file__)

inject_all_styles(get_theme())
render_sidebar()

_role = st.session_state.get("user_role", "")
_hosp_id = st.session_state.get("user_hospital_id")
_uid = int(st.session_state.get("user_id", 0))

# ── Title Block ──
st.markdown("""
<div style="margin-bottom:24px">
    <h1 style="font-family:'Syne',sans-serif;font-size:1.6rem;margin:0">AI Intelligence Center</h1>
    <p style="color:var(--text-secondary);font-size:0.82rem;margin:4px 0 0">
        Advanced predictions, logistics advisor, and anomaly scanner
    </p>
</div>""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Demand Forecast",
    "Emergency Triage",
    "Chatbot",
    "Anomaly Detection",
    "Exchange Advisor",
])

# ── TAB 1: DEMAND FORECAST ──
with tab1:
    section_header("AI-Enhanced Blood Demand Forecasting", "OpenRouter LLM Analysis")

    hospitals = get_all_hospitals()
    if _hosp_id:
        hosp_options = {h["name"]: h["id"] for h in hospitals if h["id"] == _hosp_id}
    else:
        hosp_options = {h["name"]: h["id"] for h in hospitals}

    col1, col2 = st.columns(2)
    with col1:
        selected_hosp_name = st.selectbox("Hospital", list(hosp_options.keys()))
    with col2:
        blood_group = st.selectbox("Blood Group", BLOOD_GROUPS)

    selected_hosp_id = hosp_options[selected_hosp_name]
    inventory = get_blood_units(selected_hosp_id)
    current_stock = sum(u["units"] for u in inventory if u["blood_group"] == blood_group)

    alert_banner(f"Current Stock: {current_stock} units of {blood_group} at {selected_hosp_name}", "info")

    random.seed(selected_hosp_id + ord(blood_group[0]))
    historical = [round(random.uniform(1.5, 8.0), 1) for _ in range(14)]
    forecast = forecast_demand(historical, window=7, forecast_days=7)
    risk = detect_shortage_risk(current_stock, forecast)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(metric_card("7-Day Avg Forecast", f"{sum(forecast)/7:.1f} u/day", icon="Forecast", variant="default"), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("Days Until Stockout", f"{risk['days_until_stockout']}", icon="Stockout", variant="critical" if risk["days_until_stockout"] <= 3 else "default"), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Risk Level", risk["risk_level"], icon="Risk", variant="critical" if risk["risk_level"] in ("CRITICAL", "HIGH") else "default"), unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    if st.button("Get AI Analysis", key="forecast_ai", use_container_width=True):
        with st.spinner("AI analysing demand patterns..."):
            response = ai_demand_forecast(
                selected_hosp_name, blood_group, current_stock,
                historical, forecast, risk
            )
            log_ai_usage("demand_forecast", f"{selected_hosp_name}|{blood_group}", response, selected_hosp_id, _uid)
            render_ai_response(response)

# ── TAB 2: EMERGENCY TRIAGE ──
with tab2:
    section_header("AI Emergency Triage Prioritization", "Optimizing pending queues using medical clinical guidelines")
    requests = get_blood_requests(_hosp_id)
    pending = [r for r in requests if r.get("status") == "PENDING"]

    if not pending:
        alert_banner("No pending emergency requests in the queue.", "success")
    else:
        req_rows = []
        for r in pending:
            req_rows.append({
                "Patient": r.get("patient_name", "—"),
                "Blood Group": blood_badge(r.get("blood_group", "?")),
                "Units Needed": f"{r.get('units_needed', 0)}u",
                "Urgency": status_pill(r.get("urgency", "ROUTINE")),
                "Condition": r.get("patient_condition", "—")
            })
        df_req = pd.DataFrame(req_rows)
        styled_table(df_req)

        inventory_all = get_blood_units(_hosp_id)
        stock_summary: dict[str, int] = {}
        for u in inventory_all:
            stock_summary[u["blood_group"]] = stock_summary.get(u["blood_group"], 0) + u["units"]

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        if st.button("AI Triage Analysis", key="triage_ai", use_container_width=True):
            patient_list = [
                {
                    "patient": r.get("patient_name", "Unknown"),
                    "blood_group": r["blood_group"],
                    "units_needed": r["units_needed"],
                    "urgency": r.get("urgency", "ROUTINE"),
                    "condition": r.get("patient_condition", "Not specified"),
                }
                for r in pending[:10]
            ]
            with st.spinner("AI prioritising emergency queue..."):
                response = ai_emergency_triage(patient_list, stock_summary)
                log_ai_usage("emergency_triage", f"{len(patient_list)} patients", response, _hosp_id, _uid)
                render_ai_response(response)

# ── TAB 3: CHATBOT ──
with tab3:
    section_header("LIFELINE Assistant", "Real-time query agent for inventory and clinical protocols")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    inventory = get_blood_units(_hosp_id)
    inv_summary: dict[str, int] = {}
    for u in inventory:
        inv_summary[u["blood_group"]] = inv_summary.get(u["blood_group"], 0) + u["units"]

    context = {
        "hospital_name": st.session_state.get("user_hospital_name", "LIFELINE Network"),
        "inventory": inv_summary,
        "alerts": "None currently",
    }

    # ── Chat history display ──
    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_history:
            st.markdown("""
            <div class='chat-bubble-ai'>
                Hello! I am LIFELINE Assistant. Ask me about blood inventory,
                compatibility rules, donors, or clinical protocols.
            </div>
            <div style='height:12px;'></div>""", unsafe_allow_html=True)
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(
                    f"<div class='chat-bubble-user'>{msg['content']}</div>"
                    "<div style='height:10px;'></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div class='chat-bubble-ai'>{msg['content']}</div>"
                    "<div style='height:10px;'></div>",
                    unsafe_allow_html=True,
                )

    # ── Handle pending AI reply (user sent message, AI hasn't replied yet) ──
    if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "user":
        latest_user_msg = st.session_state.chat_history[-1]["content"]
        with st.spinner("Thinking..."):
            reply = ai_chatbot(latest_user_msg, context, st.session_state.chat_history[:-1])
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            log_ai_usage("chatbot", latest_user_msg[:100], reply, _hosp_id, _uid)
            st.rerun()

    # ── Input form (works reliably inside tabs, unlike st.chat_input) ──
    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    with st.form("chat_input_form", clear_on_submit=True):
        col_msg, col_btn, col_clr = st.columns([6, 1, 1])
        with col_msg:
            user_message = st.text_input(
                "Message",
                placeholder="Ask about blood inventory, compatibility, donors, protocols...",
                label_visibility="collapsed",
            )
        with col_btn:
            send = st.form_submit_button("Send", use_container_width=True)
        with col_clr:
            clear = st.form_submit_button("Clear", use_container_width=True)

    if send and user_message.strip():
        st.session_state.chat_history.append({"role": "user", "content": user_message.strip()})
        st.rerun()
    elif clear:
        st.session_state.chat_history = []
        st.rerun()

# ── TAB 4: ANOMALY DETECTION ──
with tab4:
    section_header("Anomaly Detection", "AI audit-trail and transfusion reaction pattern scanner")

    if st.button("Run Anomaly Scan", key="anomaly_ai", use_container_width=True):
        with st.spinner("Scanning logs for anomalies..."):
            transfusions = get_transfusions(_hosp_id)
            audit = get_audit_logs(50)
            inv_changes = get_inventory_changes(_hosp_id, 30)
            response = ai_anomaly_detection(transfusions, audit, inv_changes)
            log_ai_usage("anomaly_detection", "log_scan", response, _hosp_id, _uid)
            render_ai_response(response)

# ── TAB 5: EXCHANGE ADVISOR ──
with tab5:
    section_header("Smart Exchange Advisor", "Intelligent coordination recommendations")
    hospitals = get_all_hospitals()

    col1, col2, col3 = st.columns(3)
    with col1:
        hosp_names = [h["name"] for h in hospitals]
        req_hosp_name = st.selectbox("Requesting Hospital", hosp_names, key="ex_hosp")
    with col2:
        blood_grp = st.selectbox("Blood Group Needed", BLOOD_GROUPS, key="ex_bg")
    with col3:
        units_req = st.number_input("Units Required", min_value=1, max_value=50, value=5)

    if st.button("Find Best Exchange", key="exchange_ai", use_container_width=True):
        req_hosp = next((h for h in hospitals if h["name"] == req_hosp_name), None)
        if req_hosp:
            graph = build_hospital_graph(hospitals)
            all_inventory = get_blood_units()
            nearest = graph.nearest_hospitals_with_blood(req_hosp["id"], blood_grp, all_inventory)

            if nearest:
                st.markdown("<div style='font-size:0.9rem;font-weight:600;margin-bottom:8px;'>DSA Graph Results (Dijkstra-ranked):</div>", unsafe_allow_html=True)
                dsa_rows = []
                for r in nearest[:5]:
                    dsa_rows.append({
                        "Hospital": r["hospital_name"],
                        "Distance": f"{r['distance_km']} km",
                        "Available Stock": f"{r['units_available']} units"
                    })
                df_dsa = pd.DataFrame(dsa_rows)
                styled_table(df_dsa)

                st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

                with st.spinner("AI optimising exchange strategy..."):
                    routes = [
                        {
                            "hospital": r["hospital_name"],
                            "distance_km": r["distance_km"],
                            "path": [graph.nodes.get(p, {}).get("name", str(p)) for p in r["path"]],
                        }
                        for r in nearest[:3]
                    ]
                    response = ai_exchange_advisor(req_hosp_name, blood_grp, units_req, nearest[:5], routes)
                    log_ai_usage("exchange_advisor", f"{req_hosp_name}|{blood_grp}|{units_req}u", response, req_hosp["id"], _uid)
                    render_ai_response(response)
            else:
                alert_banner(f"No hospitals found with available {blood_grp} stock.", "warning")

