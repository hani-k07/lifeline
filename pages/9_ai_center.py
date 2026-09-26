"""AI Center: advisory AI on top of the deterministic engine. Every answer is labelled, PII never leaves the app."""
from __future__ import annotations

import dataclasses

import streamlit as st

from ai_engine import (
    ai_anomaly_detection,
    ai_chatbot,
    ai_demand_forecast,
    ai_emergency_triage,
    ai_exchange_advisor,
    is_error,
)
from lifeline.auth.roles import Role
from lifeline.config import get_settings
from lifeline.constants import BLOOD_GROUPS
from lifeline.engine.forecasting import shortage_risk, wma_forecast
from lifeline.engine.routing import find_sources
from lifeline.engine.triage import triage_order
from lifeline.privacy import scrub_rows, scrub_text
from lifeline.ui import charts
from lifeline.ui import components as ui
from lifeline.ui.layout import guard, page
from utils.database import (
    get_all_hospitals,
    get_audit_logs,
    get_blood_requests,
    get_blood_summary,
    get_daily_usage,
    get_inventory_events,
    get_person_names,
    get_stock_by_hospital,
    get_transfusions,
    log_ai_usage,
)
from utils.network import get_road_graph

user = page(__file__, "AI Center", "Advisory AI on top of the deterministic engine")


def _show(feature: str, summary: str, text: str, hospital_id: int | None) -> None:
    """A failed call is a warning, never an answer. A real answer is labelled advisory and logged."""
    if is_error(text):
        ui.alert_banner(text, "warning", title="AI unavailable")
        return
    log_ai_usage(feature, summary, text, hospital_id, user.id)
    ui.ai_panel(text)


with guard():
    enabled = get_settings().ai_enabled
    if not enabled:
        ui.alert_banner("No API key is configured, so the AI features are switched off. Everything else in LIFELINE works without it. "
                        "Set OPENROUTER_API_KEY in the .env file to enable them.", "info", title="AI is off")
    ui.alert_banner("AI output is advisory. The deterministic engine result is what the system acts on; a clinician decides.", "info",
                    title="How to read this page")

    hospitals = get_all_hospitals()
    if user.role is Role.SUPER_ADMIN:
        allowed = {h["name"]: h["id"] for h in hospitals}
    else:
        allowed = {h["name"]: h["id"] for h in hospitals if h["id"] == user.hospital_id}
    scope = None if user.role is Role.SUPER_ADMIN else user.hospital_id

    tab_forecast, tab_triage, tab_chat, tab_anomaly, tab_exchange = st.tabs(
        ["Demand forecast", "Emergency triage", "Assistant", "Anomaly scan", "Exchange advisor"])

    with tab_forecast:
        c1, c2 = st.columns(2)
        hospital_name = c1.selectbox("Hospital", list(allowed), key="aif_hosp")
        group = c2.selectbox("Blood group", BLOOD_GROUPS, key="aif_group")
        hospital_id = allowed[hospital_name]
        stock = get_blood_summary(hospital_id).get(group, 0)
        history = get_daily_usage(hospital_id, group, 14)
        forecast = wma_forecast(history, horizon=7, window=7)
        risk = shortage_risk(stock, forecast)
        ui.kpi_row(ui.kpi_card("In stock", f"{stock} units"), ui.kpi_card("Forecast use", f"{sum(forecast) / 7:.1f} / day"),
                   ui.kpi_card("Risk", risk.risk_level, tone="danger" if risk.risk_level in ("CRITICAL", "HIGH") else "neutral",
                               hint="stock-out beyond 7 days" if risk.days_until_stockout is None else f"stock-out in {risk.days_until_stockout} day(s)"))
        charts.show(charts.usage_forecast(history, forecast, "", height=240))
        if st.button("Get AI analysis", key="ai_forecast", disabled=not enabled):
            summary = {"risk_level": risk.risk_level, "recommended_reorder": risk.recommended_reorder,
                       "days_until_stockout": risk.days_until_stockout if risk.days_until_stockout is not None else "more than 7"}
            with st.spinner("Analysing demand patterns…"):
                _show("demand_forecast", f"{hospital_name}|{group}",
                      ai_demand_forecast(hospital_name, group, stock, history, forecast, summary), hospital_id)

    with tab_triage:
        pending = [r for r in get_blood_requests(scope) if r["status"] == "PENDING"]
        if not pending:
            ui.empty_state("Nothing to triage", "There are no pending emergency requests.", icon="✓")
        else:
            ordered = triage_order(pending)
            ui.section_header("Engine priority", "urgency first, then how long the request has waited; this is the order the system uses")
            rows = [{**r, "ref": f"Patient {i}"} for i, r in enumerate(ordered, start=1)]
            ui.data_table(rows, [ui.Col("Ref", "ref"), ui.Col("Patient", "patient_name"),
                                 ui.Col("Group", "blood_group", render=lambda v, r: ui.blood_group_badge(v)),
                                 ui.Col("Units", "units_needed", align="right"),
                                 ui.Col("Urgency", "urgency", render=lambda v, r: ui.status_pill(v)), ui.Col("Condition", "patient_condition")],
                          key="ai_triage_tbl", page_size=8)
            st.caption("The AI is sent the 'Ref' (Patient N), the group, units, urgency and a scrubbed condition: never a name.")
            if st.button("AI triage analysis", key="ai_triage", disabled=not enabled):
                names = get_person_names()
                patients = [{"patient": r["ref"], "blood_group": r["blood_group"], "units_needed": r["units_needed"],
                             "urgency": r.get("urgency", "ROUTINE"),
                             "condition": scrub_text(r.get("patient_condition") or "Not specified", names)} for r in rows[:10]]
                with st.spinner("Prioritising the queue…"):
                    _show("emergency_triage", f"{len(patients)} patients", ai_emergency_triage(patients, get_blood_summary(scope)), scope)

    with tab_chat:
        history_key = "chat_history"
        st.session_state.setdefault(history_key, [])
        chat = st.session_state[history_key]
        if not chat:
            ui.chat_bubble("ai", "Hello. Ask me about stock, ABO/Rh compatibility, storage or logistics. I cannot see patient records.")
        for message in chat:
            ui.chat_bubble(message["role"], message["content"])

        if chat and chat[-1]["role"] == "user":            # a question is waiting for its answer
            names = get_person_names()
            question = scrub_text(chat[-1]["content"], names)          # names never leave the app
            safe_history = [{**m, "content": scrub_text(m["content"], names)} for m in chat[:-1]]
            context = {"hospital_name": user.hospital_name or "LIFELINE Network", "inventory": get_blood_summary(scope), "alerts": "None currently"}
            with st.spinner("Thinking…"):
                reply = ai_chatbot(question, context, safe_history)
            if is_error(reply):
                chat.pop()
                st.session_state["chat_error"] = reply
            else:
                chat.append({"role": "assistant", "content": reply})
                log_ai_usage("chatbot", question[:100], reply, scope, user.id)
            st.rerun()
        if error := st.session_state.pop("chat_error", None):
            ui.alert_banner(error, "warning", title="AI unavailable")

        with st.form("chat_form", clear_on_submit=True):
            c_msg, c_send, c_clear = st.columns([6, 1, 1])
            text = c_msg.text_input("Message", placeholder="Ask about stock, compatibility, storage…", label_visibility="collapsed",
                                    disabled=not enabled)
            send = c_send.form_submit_button("Send", disabled=not enabled)
            clear = c_clear.form_submit_button("Clear")
        if send and text.strip():
            chat.append({"role": "user", "content": text.strip()})
            st.rerun()
        elif clear:
            chat.clear()
            st.rerun()

    with tab_anomaly:
        ui.section_header("Anomaly scan", "the AI reads a scrubbed copy of recent transfusions, audit entries and stock movements")
        if st.button("Run anomaly scan", key="ai_anomaly", disabled=not enabled):
            names = get_person_names()
            transfusions = scrub_rows(get_transfusions(scope), keep=("id", "hospital_name", "blood_group", "units", "transfused_at"),
                                      text_fields=("notes",), names=names)
            audit = scrub_rows(get_audit_logs(50), keep=("action_type", "timestamp", "user_id"), text_fields=("description",), names=names)
            events = scrub_rows(get_inventory_events(scope, 30), keep=("hospital_id", "blood_group", "event_type", "at", "actor_id"),
                                text_fields=("note",), names=names)
            with st.spinner("Scanning the logs…"):
                _show("anomaly_detection", "log_scan", ai_anomaly_detection(transfusions, audit, events), scope)

    with tab_exchange:
        c1, c2, c3 = st.columns(3)
        requester_name = c1.selectbox("Requesting hospital", list(allowed), key="aix_hosp")
        group_x = c2.selectbox("Blood group needed", BLOOD_GROUPS, key="aix_group")
        units_x = c3.number_input("Units required", min_value=1, max_value=50, value=5, key="aix_units")
        requester_id = allowed[requester_name]
        graph = get_road_graph(hospitals)
        nearest = [{**dataclasses.asdict(o), "route": [graph.nodes[n].name for n in o.path]}
                   for o in find_sources(graph, requester_id, group_x, get_stock_by_hospital(), include_source=False)]
        if not nearest:
            ui.empty_state("No supplier found", f"No other hospital holds blood a {group_x} patient can receive.", icon="!")
        else:
            ui.section_header("Road-network result", "exact group first, then compatible groups; this is what the system would use")
            ui.data_table(nearest[:5], [ui.Col("Hospital", "hospital_name"), ui.Col("Sends", "unit_group", render=lambda v, r: ui.blood_group_badge(v)),
                                        ui.Col("Match", "exact", render=lambda v, r: ui.status_pill("exact" if v else "compatible", kind="success" if v else "info")),
                                        ui.Col("In stock", "units_available", align="right"), ui.Col("Distance (km)", "distance_km", align="right")],
                          key="aix_tbl", page_size=5)
            if st.button("Ask the AI for a strategy", key="ai_exchange", disabled=not enabled):
                routes = [{"hospital": r["hospital_name"], "distance_km": r["distance_km"], "path": r["route"], "blood_group_sent": r["unit_group"]}
                          for r in nearest[:3]]
                options = [{k: v for k, v in r.items() if k not in ("path", "route")} for r in nearest[:5]]
                with st.spinner("Optimising the exchange…"):
                    _show("exchange_advisor", f"{requester_name}|{group_x}|{int(units_x)}u",
                          ai_exchange_advisor(requester_name, group_x, int(units_x), options, routes), requester_id)
