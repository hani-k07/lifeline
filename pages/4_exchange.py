# pages/4_exchange.py
"""Blood Exchange Network — LIFELINE v6.0"""
from __future__ import annotations

import dataclasses
import html

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Exchange — LIFELINE", layout="wide")

from utils.styles import (
    inject_all_styles, get_theme, section_header, alert_banner,
    blood_badge, status_pill, styled_table,
)
from lifeline.auth.rbac import require_page
from lifeline.auth.roles import Role
from utils.sidebar import render_sidebar
from lifeline.services.exchanges import cancel_exchange, complete_exchange, request_exchange, respond_exchange
from utils.actions import attempt
from utils.database import get_all_hospitals, get_exchanges, get_stock_by_hospital
from utils.network import get_road_graph
from lifeline.constants import BLOOD_GROUPS, LOW_UNITS
from lifeline.engine.matching import exchange_match
from lifeline.engine.routing import find_sources

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
    <h1 style="font-family:'Syne',sans-serif;font-size:1.6rem;margin:0">Blood Exchange</h1>
    <p style="color:var(--text-secondary);font-size:0.82rem;margin:4px 0 0">
        Inter-hospital blood transfers powered by Dijkstra graph routing
    </p>
</div>""", unsafe_allow_html=True)

tab1, tab2, tab_suggest = st.tabs(["Find & Request Exchange", "Exchange History", "Network Suggestions"])

with tab1:
    hospitals = get_all_hospitals()

    col1, col2, col3 = st.columns(3)
    with col1:
        if _role == Role.SUPER_ADMIN:
            src_name = st.selectbox("From Hospital (Requesting)", [h["name"] for h in hospitals])
        else:
            src_name = _hosp_name
            alert_banner(f"Requesting hospital: {src_name}", "info")
    with col2:
        blood_grp = st.selectbox("Blood Group Needed", BLOOD_GROUPS)
    with col3:
        units_req = st.number_input("Units Required", min_value=1, max_value=100, value=5)

    find_clicked = st.button("Find Available Sources (Dijkstra)", use_container_width=True)
    if find_clicked:
        src_hosp = next((h for h in hospitals if h["name"] == src_name), None)
        if src_hosp:
            graph = get_road_graph(hospitals)
            nearest = [{**dataclasses.asdict(o), "route": " → ".join(graph.nodes[n].name for n in o.path)}
                       for o in find_sources(graph, src_hosp["id"], blood_grp, get_stock_by_hospital(), include_source=False)]

            if nearest:
                st.session_state["exchange_results"] = nearest
                st.session_state["exchange_src"] = src_hosp
                st.session_state["exchange_bg"] = blood_grp
                st.session_state["exchange_units"] = units_req
            else:
                alert_banner(f"No hospitals in the network have available {blood_grp} stock.", "warning")

    # Show results
    if "exchange_results" in st.session_state:
        results = st.session_state["exchange_results"]
        src = st.session_state["exchange_src"]
        bg = st.session_state["exchange_bg"]
        needed = st.session_state["exchange_units"]

        section_header(f"Results", f"{len(results)} hospitals with {bg}")

        for r in results[:6]:
            with st.container():
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                c1.markdown(f"<div style='font-size:0.95rem;font-weight:600;'>{html.escape(r['hospital_name'])}</div>"
                            f"{blood_badge(r['unit_group'])} <span style='font-size:0.72rem'>{'exact' if r['exact'] else 'compatible'}</span>",
                            unsafe_allow_html=True)
                c2.markdown(f"<span style='font-family:monospace;font-size:0.85rem;'>{r['distance_km']} km</span>", unsafe_allow_html=True)
                c3.markdown(f"<span style='font-family:monospace;font-size:0.85rem;'>{r['units_available']} units</span>", unsafe_allow_html=True)
                c4.markdown(f"<span style='font-family:monospace;font-size:0.85rem;'>~{int(round(r['eta_min']))} min ETA</span>", unsafe_allow_html=True)
                st.caption(f"Route: {r['route']}")

                if st.button(f"Request {r['unit_group']} from {r['hospital_name']}", key=f"req_{r['hospital_id']}_{r['unit_group']}"):
                    ok, ex_error, _ = attempt(request_exchange, user, r["hospital_id"], src["id"], r["unit_group"],
                                              min(int(needed), r["units_available"]))
                    if ok:
                        st.toast(f"Exchange request sent to {r['hospital_name']}")
                        del st.session_state["exchange_results"]
                        st.rerun()
                    alert_banner(ex_error or "Could not send the request.", "danger")
                st.divider()

with tab2:
    exchanges = get_exchanges(_hosp_id if _role != Role.SUPER_ADMIN else None)
    if not exchanges:
        alert_banner("No exchange transactions recorded yet.", "info")
    else:
        styled_table(pd.DataFrame([{
            "#": ex["id"],
            "From (supplier)": ex.get("from_name", "—"),
            "To (requester)": ex.get("to_name", "—"),
            "Blood Group": blood_badge(ex.get("blood_group", "?")),
            "Units": ex.get("units", 0),
            "Status": status_pill(ex.get("status", "PENDING")),
            "Created": ex.get("created_at", "")[:16].replace("T", " ") if ex.get("created_at") else "—",
        } for ex in exchanges]))

        open_ex = [ex for ex in exchanges if ex["status"] in ("PENDING", "ACCEPTED")]
        if open_ex:
            section_header("Open exchanges", "Suppliers accept or reject; either side completes once units are handed over")
            action_error = None
            for ex in open_ex:
                label = f"#{ex['id']} · {ex['units']}u {ex['blood_group']} · {ex['from_name']} → {ex['to_name']}"
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.markdown(f"{label} {status_pill(ex['status'])}", unsafe_allow_html=True)
                is_supplier = _role == Role.SUPER_ADMIN or ex["from_hospital_id"] == _hosp_id
                if ex["status"] == "PENDING" and is_supplier:
                    if c2.button("Accept", key=f"acc_{ex['id']}"):
                        ok, action_error, _ = attempt(respond_exchange, user, ex["id"], True)
                        if ok:
                            st.toast("Exchange accepted; units reserved")
                            st.rerun()
                    if c3.button("Reject", key=f"rej_{ex['id']}"):
                        ok, action_error, _ = attempt(respond_exchange, user, ex["id"], False)
                        if ok:
                            st.rerun()
                if ex["status"] == "ACCEPTED":
                    if c2.button("Complete", key=f"done_{ex['id']}"):
                        ok, action_error, _ = attempt(complete_exchange, user, ex["id"])
                        if ok:
                            st.toast("Exchange completed; units transferred")
                            st.rerun()
                    if c3.button("Cancel", key=f"xcl_{ex['id']}"):
                        ok, action_error, _ = attempt(cancel_exchange, user, ex["id"])
                        if ok:
                            st.rerun()
            if action_error:
                alert_banner(action_error, "danger")

with tab_suggest:
    section_header("Suggested transfers", "Hospitals below the low-stock level are matched with hospitals holding more than twice that level")
    stock = get_stock_by_hospital()
    names_by_id = {h["id"]: h["name"] for h in hospitals}
    key_groups = ("A+", "B+", "O+", "O-")
    shortages = [{"hospital_id": h, "blood_group": g, "units": LOW_UNITS - stock.get(h, {}).get(g, 0)}
                 for h in names_by_id for g in key_groups if stock.get(h, {}).get(g, 0) < LOW_UNITS]
    surpluses = [{"hospital_id": h, "blood_group": g, "units": n - 2 * LOW_UNITS}
                 for h, groups in stock.items() for g, n in groups.items() if n > 2 * LOW_UNITS]
    graph = get_road_graph(hospitals)
    dist_cache: dict[int, dict[int, float]] = {}

    def road_km(a: int, b: int) -> float:
        if a not in dist_cache:
            dist_cache[a] = graph.dijkstra(a)[0]
        return dist_cache[a].get(b, float("inf"))

    plan = exchange_match(shortages, surpluses, road_km)
    if not plan["matches"]:
        alert_banner("No transfers to suggest: no shortage can be covered from a surplus right now.", "info")
    else:
        suggest_error = None
        for i, m in enumerate(plan["matches"][:12]):
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"{blood_badge(m['unit_group'])} {m['units']}u · {html.escape(names_by_id[m['from_hospital_id']])} → "
                        f"{html.escape(names_by_id[m['to_hospital_id']])} · {m['distance_km']} km"
                        f"{'' if m['exact'] else ' · compatible substitute for ' + m['needed_group']}", unsafe_allow_html=True)
            if _role == Role.SUPER_ADMIN or m["to_hospital_id"] == _hosp_id:
                if c2.button("Request", key=f"sug_{i}"):
                    ok, suggest_error, _ = attempt(request_exchange, user, m["from_hospital_id"], m["to_hospital_id"],
                                                   m["unit_group"], m["units"])
                    if ok:
                        st.toast("Exchange request sent")
                        st.rerun()
        if suggest_error:
            alert_banner(suggest_error, "danger")
    if plan["unmet"]:
        st.caption(f"{len(plan['unmet'])} shortage(s) cannot be covered from the network's surplus: consider a supplier order.")
