# pages/3_emergency.py
"""Emergency Blood Requests — LIFELINE v6.0"""
from __future__ import annotations

import dataclasses
import html

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Emergency — LIFELINE", layout="wide")

from lifeline.constants import BLOOD_GROUPS
from lifeline.engine.routing import backup_hospitals, find_sources
from lifeline.engine.triage import triage_order
from lifeline.auth.rbac import require_page
from lifeline.auth.roles import Role
from lifeline.services.emergency import cancel_request, create_request, fulfil_request, reserve_units
from utils.actions import attempt
from utils.database import get_all_hospitals, get_blood_requests, get_reserved_counts
from utils.database import get_stock_by_hospital
from utils.network import get_road_graph
from utils.sidebar import render_sidebar
from utils.styles import (
    alert_banner,
    blood_badge,
    get_theme,
    inject_all_styles,
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
    <h1 style="font-family:'Syne',sans-serif;font-size:1.6rem;margin:0">Emergency Requests</h1>
    <p style="color:var(--text-secondary);font-size:0.82rem;margin:4px 0 0">
        Submit and manage critical blood requests with DSA triage queue
    </p>
</div>""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["Active Queue", "New Request", "Find Blood"])
_scope = None if _role == Role.SUPER_ADMIN else _hosp_id
_can_manage = _role in (Role.SUPER_ADMIN, Role.HOSPITAL_ADMIN)

# ── Tab 1: Queue ──
with tab1:
    requests = get_blood_requests(_scope)
    active = [r for r in requests if r.get("status") in ("PENDING", "RESERVED")]
    closed = [r for r in requests if r.get("status") in ("RESOLVED", "CANCELLED")]
    reserved_counts = get_reserved_counts()

    section_header("Active Queue", f"{len(active)} open requests")
    queue_error = None

    if not active:
        alert_banner("No open emergency requests in the queue.", "success")
    else:
        for req in triage_order(active):
            rid, need = req["id"], req["units_needed"]
            have = reserved_counts.get(rid, 0)
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([2, 1, 1.2, 1.5, 1.4])
                pt = html.escape(str(req.get("patient_name") or "Unknown"))
                cond = html.escape(str(req.get("patient_condition") or "N/A"))
                ts = str(req.get("created_at", ""))[:16].replace("T", " ")
                c1.markdown(f"<div style='font-size:0.9rem;font-weight:600;color:var(--text-primary)'>{pt}</div>"
                            f"<div style='font-size:0.75rem;color:var(--text-secondary)'>{cond}</div>", unsafe_allow_html=True)
                c2.markdown(status_pill(req.get("urgency", "ROUTINE")) + " " + status_pill(req["status"]), unsafe_allow_html=True)
                c3.markdown(f"{blood_badge(req['blood_group'])} <span style='font-family:monospace;font-size:0.85rem'>"
                            f"{have}/{need}u reserved</span>", unsafe_allow_html=True)
                c4.markdown(f"<div style='font-size:0.75rem;color:var(--text-secondary)'>{html.escape(req.get('hospital_name', '—'))}"
                            f"</div><div style='font-size:0.68rem;color:var(--text-secondary)'>{ts}</div>", unsafe_allow_html=True)
                if _can_manage:
                    with c5:
                        if req["status"] == "RESERVED" and have == need and st.button("Dispatch", key=f"disp_{rid}"):
                            ok, queue_error, _ = attempt(fulfil_request, user, rid)
                            if ok:
                                st.toast(f"Request {rid} dispatched")
                                st.rerun()
                        if st.button("Cancel", key=f"cancel_{rid}"):
                            ok, queue_error, _ = attempt(cancel_request, user, rid, "cancelled from queue")
                            if ok:
                                st.toast(f"Request {rid} cancelled; reserved units returned to stock")
                                st.rerun()
                st.divider()
    if queue_error:
        alert_banner(queue_error, "danger")

    if closed:
        with st.expander(f"Closed Requests ({len(closed)})"):
            styled_table(pd.DataFrame([{
                "Patient": r["patient_name"],
                "Blood Group": blood_badge(r["blood_group"]),
                "Units": r["units_needed"],
                "Urgency": status_pill(r["urgency"]),
                "Status": status_pill(r["status"]),
                "Requested": r["created_at"][:16].replace("T", " ") if r.get("created_at") else "—",
                "Closed": r["resolved_at"][:16].replace("T", " ") if r.get("resolved_at") else "—",
            } for r in closed]))

# ── Tab 2: New Request ──
with tab2:
    section_header("Submit Emergency Blood Request")
    new_error = None

    with st.form("emergency_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            bg = st.selectbox("Blood Group Needed", BLOOD_GROUPS)
        with col2:
            units = st.number_input("Units Required", min_value=1, max_value=50, value=2)
        with col3:
            urgency = st.selectbox("Urgency Level", ["CRITICAL", "URGENT", "ROUTINE"])

        patient_name = st.text_input("Patient Name")
        condition = st.text_area("Patient Condition / Notes", placeholder="e.g. Trauma surgery, O- required")

        if _role == Role.SUPER_ADMIN:
            hosp_map = {h["name"]: h["id"] for h in get_all_hospitals()}
            req_hosp_id = hosp_map[st.selectbox("Requesting Hospital", list(hosp_map.keys()))]
        else:
            req_hosp_id = _hosp_id

        if st.form_submit_button("Submit Emergency Request", use_container_width=True):
            ok, new_error, _ = attempt(create_request, user, req_hosp_id, bg, int(units), urgency, patient_name, condition)
            if ok:
                st.toast(f"{urgency} request submitted for {units} unit(s) of {bg}")
                st.rerun()
    if new_error:
        alert_banner(new_error, "danger")

# ── Tab 3: Find Blood (Dijkstra) + reserve ──
with tab3:
    section_header("Find Blood via Network Graph (Dijkstra)")
    hospitals = get_all_hospitals()

    col1, col2, col3 = st.columns(3)
    with col1:
        hosp_names = [h["name"] for h in hospitals]
        default_idx = next((i for i, h in enumerate(hospitals) if h["id"] == _hosp_id), 0)
        src_name = st.selectbox("Your Hospital", hosp_names, index=default_idx)
    with col2:
        need_bg = st.selectbox("Blood Group Needed", BLOOD_GROUPS, key="find_bg")
    with col3:
        need_units = st.number_input("Units Needed", min_value=1, max_value=50, value=3)

    if st.button("Find Nearest Blood Source", use_container_width=True):
        src_hosp = next((h for h in hospitals if h["name"] == src_name), None)
        if src_hosp:
            graph = get_road_graph(hospitals)
            options = find_sources(graph, src_hosp["id"], need_bg, get_stock_by_hospital())    # one Dijkstra run
            st.session_state["em_results"] = {
                "group": need_bg, "units": int(need_units), "source_id": src_hosp["id"],
                "rows": [{**dataclasses.asdict(o), "route": " → ".join(graph.nodes[n].name for n in o.path)} for o in options],
                "backups": backup_hospitals(graph, src_hosp["id"]),
            }

    found = st.session_state.get("em_results")
    if found:
        if not found["rows"]:
            alert_banner(f"No hospital in the network holds blood that a {found['group']} patient can safely receive.", "danger")
        else:
            exact = sum(1 for r in found["rows"] if r["exact"])
            alert_banner(f"{len(found['rows'])} source(s) found: {exact} with exact {found['group']}, "
                         f"{len(found['rows']) - exact} with compatible groups.", "success")
            styled_table(pd.DataFrame([{
                "Hospital": r["hospital_name"],
                "Sends": blood_badge(r["unit_group"]),
                "Match": "exact" if r["exact"] else "compatible",
                "Stock": f"{r['units_available']} units",
                "Distance": f"{r['distance_km']} km",
                "ETA": f"~{int(round(r['eta_min']))} min",
                "Route": r["route"],
            } for r in found["rows"][:8]]))
            if found["backups"]:
                with st.expander("Backup hospitals (fewest road hops first)"):
                    styled_table(pd.DataFrame([{"Hospital": b["name"], "Hops": b["level"], "Distance": f"{b['distance_km']} km"}
                                               for b in found["backups"][:6]]))

            open_requests = [r for r in get_blood_requests(_scope)
                             if r["status"] in ("PENDING", "RESERVED") and r["blood_group"] == found["group"]]
            if open_requests:
                section_header("Reserve for an open request")
                labels = {f"#{r['id']} · {r['patient_name']} · {r['units_needed']}u {r['blood_group']}": r for r in open_requests}
                chosen = labels[st.selectbox("Request", list(labels.keys()))]
                reserve_error = None
                for r in found["rows"][:8]:
                    take = min(chosen["units_needed"], r["units_available"])
                    label = f"Reserve {take} × {r['unit_group']} from {r['hospital_name']}"
                    if st.button(label, key=f"resv_{r['hospital_id']}_{r['unit_group']}"):
                        ok, reserve_error, _ = attempt(reserve_units, user, chosen["id"], r["hospital_id"], r["unit_group"], take)
                        if ok:
                            st.toast(f"Reserved {take} unit(s) at {r['hospital_name']}")
                            st.rerun()
                if reserve_error:
                    alert_banner(reserve_error, "danger")
            else:
                st.caption(f"No open {found['group']} request to reserve for. Create one in the 'New Request' tab.")
