"""Exchange: ask another hospital for blood, answer requests, and see suggested transfers."""
from __future__ import annotations

import dataclasses

import streamlit as st

from lifeline.auth.roles import Role
from lifeline.constants import BLOOD_GROUPS, KEY_GROUPS, LOW_UNITS
from lifeline.engine.matching import exchange_match
from lifeline.engine.routing import find_sources
from lifeline.services.exchanges import cancel_exchange, complete_exchange, request_exchange, respond_exchange
from lifeline.ui import components as ui
from lifeline.ui.layout import guard, page
from utils.actions import attempt
from utils.database import get_all_hospitals, get_exchanges, get_stock_by_hospital
from utils.network import get_road_graph

user = page(__file__, "Exchange", "Ask another hospital for blood, answer requests, balance the network")

with guard():
    hospitals = get_all_hospitals()
    names = {h["id"]: h["name"] for h in hospitals}
    tab_request, tab_open, tab_suggest = st.tabs(["Request blood", "Exchanges", "Network suggestions"])

    with tab_request:
        if user.role is Role.SUPER_ADMIN:
            by_name = {h["name"]: h["id"] for h in hospitals}
            requester_id = by_name[st.selectbox("Requesting hospital", list(by_name), key="ex_hosp")]
        else:
            requester_id = user.hospital_id
            st.text_input("Requesting hospital", value=user.hospital_name, disabled=True)
        c1, c2 = st.columns(2)
        group = c1.selectbox("Blood group needed", BLOOD_GROUPS, key="ex_group")
        units = c2.number_input("Units needed", min_value=1, max_value=100, value=5, step=1, key="ex_units")
        if st.button("Find sources", type="primary", key="ex_find"):
            graph = get_road_graph(hospitals)
            rows = [{**dataclasses.asdict(o), "route": " → ".join(graph.nodes[n].name for n in o.path)}
                    for o in find_sources(graph, requester_id, group, get_stock_by_hospital(), include_source=False)]
            st.session_state["ex_found"] = {"rows": rows, "group": group, "units": int(units), "requester": requester_id}

        found = st.session_state.get("ex_found")
        if found:
            if not found["rows"]:
                ui.empty_state("No hospital can supply this group", "No other hospital holds blood this patient group can receive.", icon="!")
            else:
                ui.data_table(
                    found["rows"],
                    [ui.Col("Hospital", "hospital_name"), ui.Col("Sends", "unit_group", render=lambda v, r: ui.blood_group_badge(v)),
                     ui.Col("Match", "exact", render=lambda v, r: ui.status_pill("exact" if v else "compatible", kind="success" if v else "info")),
                     ui.Col("In stock", "units_available", align="right"), ui.Col("Distance (km)", "distance_km", align="right"),
                     ui.Col("ETA (min)", "eta_min", align="right"), ui.Col("Route", "route", sortable=False)],
                    key="ex_opts", page_size=8)
                labels = [f"{r['hospital_name']} · {r['unit_group']} · {r['units_available']} in stock" for r in found["rows"]]
                pick = found["rows"][labels.index(st.selectbox("Ask this hospital", labels, key="ex_pick"))]
                ask = st.number_input("Units to ask for", min_value=1, max_value=pick["units_available"],
                                      value=min(found["units"], pick["units_available"]), step=1, key="ex_ask")
                if ui.confirm_dialog("ex_req", "Send exchange request",
                                     f"Ask {pick['hospital_name']} for {int(ask)} × {pick['unit_group']}? They must accept before units are reserved.",
                                     confirm_label="Yes, send"):
                    ok, error, _ = attempt(request_exchange, user, pick["hospital_id"], found["requester"], pick["unit_group"], int(ask))
                    if ok:
                        st.session_state.pop("ex_found", None)
                        st.toast(f"Request sent to {pick['hospital_name']}")
                        st.rerun()
                    ui.alert_banner(error or "Could not send the request.", "danger")

    with tab_open:
        scope = None if user.role is Role.SUPER_ADMIN else user.hospital_id
        exchanges = get_exchanges(scope)
        ui.data_table(
            exchanges,
            [ui.Col("#", "id", align="right"), ui.Col("Supplier", "from_name"), ui.Col("Requester", "to_name"),
             ui.Col("Group", "blood_group", render=lambda v, r: ui.blood_group_badge(v)), ui.Col("Units", "units", align="right"),
             ui.Col("Status", "status", render=lambda v, r: ui.status_pill(v)),
             ui.Col("Created", "created_at", render=lambda v, r: str(v)[:16].replace("T", " "))],
            key="ex_hist", empty_title="No exchanges yet", empty_body="Requests you send or receive are listed here.")
        active = [e for e in exchanges if e["status"] in ("PENDING", "ACCEPTED")]
        if active:
            ui.section_header("Needs action", "suppliers accept or reject; either side completes once the units are handed over")
            action_error = None
            for ex in active:
                is_supplier = user.role is Role.SUPER_ADMIN or ex["from_hospital_id"] == user.hospital_id
                c1, c2, c3 = st.columns([4, 1.4, 1.4])
                c1.markdown(f"#{ex['id']} · {ex['units']} × {ui.blood_group_badge(ex['blood_group'])} · {ui.esc(ex['from_name'])} → "
                            f"{ui.esc(ex['to_name'])} {ui.status_pill(ex['status'])}", unsafe_allow_html=True)
                with c2:
                    if ex["status"] == "PENDING" and is_supplier and ui.confirm_dialog(
                            f"acc_{ex['id']}", "Accept", f"Accept exchange #{ex['id']}? {ex['units']} unit(s) will be reserved for it.",
                            confirm_label="Yes, accept"):
                        ok, action_error, _ = attempt(respond_exchange, user, ex["id"], True)
                        if ok:
                            st.toast("Exchange accepted; units reserved")
                            st.rerun()
                    if ex["status"] == "ACCEPTED" and ui.confirm_dialog(
                            f"done_{ex['id']}", "Complete", f"Complete exchange #{ex['id']}? The units move to the requesting hospital.",
                            confirm_label="Yes, complete"):
                        ok, action_error, _ = attempt(complete_exchange, user, ex["id"])
                        if ok:
                            st.toast("Exchange completed; units transferred")
                            st.rerun()
                with c3:
                    if ex["status"] == "PENDING" and is_supplier and ui.confirm_dialog(
                            f"rej_{ex['id']}", "Reject", f"Reject exchange #{ex['id']}?", confirm_label="Yes, reject", danger=True):
                        ok, action_error, _ = attempt(respond_exchange, user, ex["id"], False)
                        if ok:
                            st.rerun()
                    if ex["status"] == "ACCEPTED" and ui.confirm_dialog(
                            f"xcl_{ex['id']}", "Cancel", f"Cancel exchange #{ex['id']}? Reserved units are released.",
                            confirm_label="Yes, cancel", danger=True):
                        ok, action_error, _ = attempt(cancel_exchange, user, ex["id"])
                        if ok:
                            st.rerun()
            if action_error:
                ui.alert_banner(action_error, "danger")

    with tab_suggest:
        ui.section_header("Suggested transfers", "hospitals below the low-stock level, matched with hospitals holding more than twice that level")
        stock = get_stock_by_hospital()
        shortages = [{"hospital_id": h, "blood_group": g, "units": LOW_UNITS - stock.get(h, {}).get(g, 0)}
                     for h in names for g in KEY_GROUPS if stock.get(h, {}).get(g, 0) < LOW_UNITS]
        surpluses = [{"hospital_id": h, "blood_group": g, "units": n - 2 * LOW_UNITS}
                     for h, by_group in stock.items() for g, n in by_group.items() if n > 2 * LOW_UNITS]
        graph = get_road_graph(hospitals)
        cache: dict[int, dict[int, float]] = {}

        def road_km(a: int, b: int) -> float:
            if a not in cache:
                cache[a] = graph.dijkstra(a)[0]
            return cache[a].get(b, float("inf"))

        plan = exchange_match(shortages, surpluses, road_km)
        if not plan["matches"]:
            ui.empty_state("No transfers to suggest", "No shortage can be covered from a surplus right now.", icon="✓")
        else:
            rows = [{**m, "from": names[m["from_hospital_id"]], "to": names[m["to_hospital_id"]]} for m in plan["matches"]]
            ui.data_table(
                rows,
                [ui.Col("From", "from"), ui.Col("To", "to"), ui.Col("Group", "unit_group", render=lambda v, r: ui.blood_group_badge(v)),
                 ui.Col("Units", "units", align="right"), ui.Col("Distance (km)", "distance_km", align="right"),
                 ui.Col("Note", "exact", render=lambda v, r: "" if v else f"substitute for {r['needed_group']}", search=False)],
                key="ex_sugg", page_size=8)
            allowed = [m for m in plan["matches"] if user.role is Role.SUPER_ADMIN or m["to_hospital_id"] == user.hospital_id]
            if allowed:
                labels = [f"{names[m['from_hospital_id']]} → {names[m['to_hospital_id']]} · {m['units']} × {m['unit_group']}" for m in allowed]
                choice = allowed[labels.index(st.selectbox("Turn a suggestion into a request", labels, key="ex_sugg_pick"))]
                if ui.confirm_dialog("ex_sugg_go", "Send this request", f"Ask {names[choice['from_hospital_id']]} for {choice['units']} × {choice['unit_group']}?",
                                     confirm_label="Yes, send"):
                    ok, error, _ = attempt(request_exchange, user, choice["from_hospital_id"], choice["to_hospital_id"],
                                           choice["unit_group"], choice["units"])
                    if ok:
                        st.toast("Exchange request sent")
                        st.rerun()
                    ui.alert_banner(error or "Could not send the request.", "danger")
        if plan["unmet"]:
            st.caption(f"{len(plan['unmet'])} shortage(s) cannot be covered from the network's surplus: consider a supplier order.")
