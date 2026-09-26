"""Emergency: a three-step flow. 1) who needs what  2) ranked, compatible sources + route  3) confirm."""
from __future__ import annotations

import dataclasses
from typing import Any

import streamlit as st

from lifeline.auth.roles import Role
from lifeline.auth.session import CurrentUser
from lifeline.constants import BLOOD_GROUPS
from lifeline.engine.routing import backup_hospitals, find_sources
from lifeline.engine.triage import triage_order
from lifeline.services.emergency import cancel_request, create_and_reserve, fulfil_request
from lifeline.ui import charts
from lifeline.ui import components as ui
from lifeline.ui.layout import guard, page
from utils.actions import attempt
from utils.database import get_all_hospitals, get_blood_requests, get_reserved_counts, get_stock_by_hospital
from utils.network import get_road_graph

user = page(__file__, "Emergency", "Find safe blood fast, reserve it, then dispatch")

FLOW = "em_flow"
STEPS = ["Patient & need", "Sources & route", "Confirm"]


def _flow() -> dict[str, Any]:
    return st.session_state.setdefault(FLOW, {"step": 1})


def _plan(options: list[dict], chosen: list[int], units: int) -> list[dict]:
    """Allocate `units` across the chosen options in ranked order (exact group first, then nearest)."""
    plan, remaining = [], units
    for i in sorted(chosen):
        if remaining <= 0:
            break
        option = options[i]
        take = min(remaining, option["units_available"])
        plan.append({**option, "take": take})
        remaining -= take
    return plan


def _suggested(options: list[dict], units: int) -> list[int]:
    picked, remaining = [], units
    for i, option in enumerate(options):
        if remaining <= 0:
            break
        picked.append(i)
        remaining -= option["units_available"]
    return picked


def _go(step: int) -> None:
    """Button callback: move between steps without a half-rendered intermediate pass."""
    st.session_state[FLOW]["step"] = step


def _search(hospitals: list[dict], hospital_id: int, hospital_name: str) -> None:
    """Button callback: validate step 1, run the search, move to step 2. The typed values are kept for 'Back'."""
    ss = st.session_state
    flow = ss[FLOW]
    need = {"hospital_id": hospital_id, "hospital_name": hospital_name, "group": ss["em_group"], "units": int(ss["em_units"]),
            "urgency": ss["em_urgency"], "patient": ss["em_patient"].strip(), "condition": ss["em_condition"].strip()}
    flow["need"] = need
    if not need["patient"]:
        flow["errors"] = {"patient": "Enter the patient's name, or a reference if they are unidentified."}
        return
    graph = get_road_graph(hospitals)
    flow.update(step=2, options=[{**dataclasses.asdict(o), "route": " → ".join(graph.nodes[n].name for n in o.path)}
                                 for o in find_sources(graph, hospital_id, need["group"], get_stock_by_hospital())],
                backups=backup_hospitals(graph, hospital_id))


def _confirm(actor: CurrentUser) -> None:
    """Button callback: create the request and reserve every planned unit in one transaction."""
    flow = st.session_state[FLOW]
    need = flow["need"]
    sources = [(p["hospital_id"], p["unit_group"], p["take"]) for p in flow["plan"]]
    ok, error, result = attempt(create_and_reserve, actor, need["hospital_id"], need["group"], need["units"], need["urgency"],
                                need["patient"], need["condition"], sources)
    if ok:
        request_id, codes = result
        flow.update(step=4, done={"request_id": request_id, "codes": codes})
        st.toast(f"Request #{request_id} created; {len(codes)} unit(s) reserved")
    else:
        flow["error"] = error


def _restart() -> None:
    st.session_state[FLOW] = {"step": 1}


def _step_need(flow: dict[str, Any], hospitals: list[dict]) -> None:
    errors = flow.pop("errors", {})
    prior = flow.get("need", {})                      # what the user typed before pressing Back
    if user.role is Role.SUPER_ADMIN:
        names = {h["name"]: h["id"] for h in hospitals}
        picked = st.selectbox("Requesting hospital", list(names), key="em_hosp",
                              index=list(names).index(prior["hospital_name"]) if prior.get("hospital_name") in names else 0)
        hospital_id, hospital_name = names[picked], picked
    else:
        hospital_id, hospital_name = user.hospital_id, user.hospital_name
        st.text_input("Requesting hospital", value=hospital_name, disabled=True)
    assert hospital_id is not None
    urgencies = ["CRITICAL", "URGENT", "ROUTINE"]
    c1, c2, c3 = st.columns(3)
    c1.selectbox("Patient blood group", BLOOD_GROUPS, key="em_group", index=BLOOD_GROUPS.index(prior.get("group", BLOOD_GROUPS[0])))
    c2.number_input("Units needed", min_value=1, max_value=20, value=prior.get("units", 2), step=1, key="em_units")
    c3.radio("Urgency", urgencies, horizontal=True, key="em_urgency", index=urgencies.index(prior.get("urgency", "CRITICAL")))
    st.text_input("Patient name or reference", key="em_patient", value=prior.get("patient", ""), help="Shown only to staff of this hospital.")
    ui.field_error(errors.get("patient"))
    st.text_area("Clinical notes (optional)", key="em_condition", value=prior.get("condition", ""), height=80,
                 placeholder="e.g. road accident, haemorrhage, O- preferred")
    st.button("Find blood sources", type="primary", key="em_find", on_click=_search, args=(hospitals, hospital_id, hospital_name))


def _step_sources(flow: dict[str, Any], hospitals: list[dict]) -> None:
    need, options = flow["need"], flow["options"]
    ui.alert_banner(f"{need['units']} unit(s) of {need['group']} for {need['hospital_name']} · {need['urgency']}", "info", title="Need")
    if not options:
        ui.empty_state("No compatible blood in the network", f"No hospital holds blood a {need['group']} patient can safely receive. "
                       "Contact the regional blood bank.", icon="!")
        st.button("← Change the request", key="em_back1", on_click=_go, args=(1,))
        return

    exact = sum(1 for o in options if o["exact"])
    ui.alert_banner(f"{len(options)} source(s): {exact} with the exact group, {len(options) - exact} compatible substitute(s). "
                    "Exact matches are ranked first; O- is kept for last.", "success", title="Found")
    ui.data_table(
        options,
        [ui.Col("Hospital", "hospital_name"),
         ui.Col("Sends", "unit_group", render=lambda v, r: ui.blood_group_badge(v)),
         ui.Col("Match", "exact", render=lambda v, r: ui.status_pill("exact" if v else "compatible", kind="success" if v else "info")),
         ui.Col("In stock", "units_available", align="right"),
         ui.Col("Distance (km)", "distance_km", align="right"),
         ui.Col("ETA (min)", "eta_min", align="right"),
         ui.Col("Route", "route", sortable=False)],
        key="em_opts", page_size=8)

    labels = [f"{o['hospital_name']} · {o['unit_group']} · {o['units_available']} in stock · {o['distance_km']} km" for o in options]
    default = [labels[i] for i in _suggested(options, need["units"])]
    picked = st.multiselect("Sources to reserve from", labels, default=default, key="em_pick",
                            help="Reserved in ranked order until the units needed are covered.")
    plan = _plan(options, [labels.index(p) for p in picked], need["units"])
    covered = sum(p["take"] for p in plan)
    if covered >= need["units"]:
        ui.alert_banner(f"The plan covers all {need['units']} unit(s).", "success", title="Plan")
    else:
        ui.alert_banner(f"The plan covers {covered} of {need['units']} unit(s). Add another source.", "warning", title="Plan")
    if plan:
        ui.render(ui.html_table(plan, [ui.Col("Reserve at", "hospital_name"), ui.Col("Group", "unit_group", render=lambda v, r: ui.blood_group_badge(v)),
                                       ui.Col("Units", "take", align="right"), ui.Col("ETA (min)", "eta_min", align="right"),
                                       ui.Col("Route", "route")]))
        graph = get_road_graph(hospitals)
        route = [(graph.nodes[n].lat, graph.nodes[n].lon) for n in plan[0]["path"]]
        edges = [(graph.nodes[a].lat, graph.nodes[a].lon, graph.nodes[b].lat, graph.nodes[b].lon) for a, b, _ in graph.edges()]
        charts.show(charts.route_map(hospitals, edges, route, height=340))
        st.caption(f"Highlighted: fastest route from {plan[0]['hospital_name']} to {need['hospital_name']} "
                   f"({plan[0]['distance_km']} km, about {int(round(plan[0]['eta_min']))} min).")
    with st.expander("Backup hospitals (fewest road hops first)"):
        ui.data_table(flow["backups"], [ui.Col("Hospital", "name"), ui.Col("Hops", "level", align="right"),
                                        ui.Col("Distance (km)", "distance_km", align="right")], key="em_backup", page_size=6)

    flow["plan"] = plan
    b1, b2 = st.columns(2)
    b1.button("← Back", key="em_back2", on_click=_go, args=(1,))
    b2.button("Review and confirm →", type="primary", key="em_next", disabled=covered < need["units"], on_click=_go, args=(3,))


def _step_confirm(flow: dict[str, Any]) -> None:
    need, plan = flow["need"], flow["plan"]
    ui.kpi_row(ui.kpi_card("Patient group", need["group"], hint=need["hospital_name"]),
               ui.kpi_card("Units", need["units"], hint=f"from {len(plan)} source(s)"),
               ui.kpi_card("Urgency", need["urgency"], tone="danger" if need["urgency"] == "CRITICAL" else "neutral"))
    ui.section_header("This will")
    ui.render(ui.html_table(plan, [ui.Col("Reserve at", "hospital_name"), ui.Col("Group", "unit_group", render=lambda v, r: ui.blood_group_badge(v)),
                                   ui.Col("Units", "take", align="right"), ui.Col("ETA (min)", "eta_min", align="right")]))
    st.markdown(f"- create an **{need['urgency']}** request for **{need['units']} × {need['group']}**\n"
                f"- reserve the units above (earliest expiry first) so nobody else can take them\n"
                f"- write the request and reservations to the audit trail")
    if any(not p["exact"] for p in plan):
        ui.alert_banner("Some units are a compatible substitute, not the patient's own group. Confirm ABO/Rh compatibility and the "
                        "cross-match per your protocol before transfusion.", "warning", title="Check")
    error = flow.pop("error", None)
    if error:
        ui.alert_banner(f"{error} Stock may have changed since the search: go back and search again. Nothing was saved.", "danger",
                        title="Could not reserve")
    b1, b2 = st.columns(2)
    b1.button("← Back", key="em_back3", on_click=_go, args=(2,))
    b2.button("Confirm and reserve", type="primary", key="em_confirm", on_click=_confirm, args=(user,))


def _step_done(flow: dict[str, Any]) -> None:
    done = flow["done"]
    ui.alert_banner(f"Request #{done['request_id']} is open and {len(done['codes'])} unit(s) are reserved for it.", "success", title="Done")
    st.write("Unit codes: " + ", ".join(done["codes"]))
    st.caption("Dispatch the request from the 'Open requests' tab when the units leave.")
    st.button("Start another emergency", type="primary", key="em_again", on_click=_restart)


def _open_requests(can_manage: bool) -> None:
    scope = None if user.role is Role.SUPER_ADMIN else user.hospital_id
    active = [r for r in get_blood_requests(scope) if r["status"] in ("PENDING", "RESERVED")]
    if not active:
        ui.empty_state("No open emergencies", "New requests appear here in triage order.", icon="✓")
        return
    reserved = get_reserved_counts()
    error = None
    for req in triage_order(active):
        rid, need = req["id"], req["units_needed"]
        have = reserved.get(rid, 0)
        c1, c2, c3 = st.columns([3, 3, 2])
        c1.markdown(f"**{ui.esc(req.get('patient_name') or 'Unknown')}**  \n{ui.esc(req.get('patient_condition') or '')}")
        c2.markdown(ui.status_pill(req["urgency"]) + " " + ui.status_pill(req["status"]) + " " + ui.blood_group_badge(req["blood_group"])
                    + f"  {have}/{need} reserved · #{rid} · {ui.esc(req['hospital_name'])}", unsafe_allow_html=True)
        if can_manage:
            with c3:
                if req["status"] == "RESERVED" and have == need and ui.confirm_dialog(
                        f"disp_{rid}", "Dispatch", f"Dispatch the {need} reserved unit(s) for request #{rid}? They will be marked as issued.",
                        confirm_label="Yes, dispatch"):
                    ok, error, _ = attempt(fulfil_request, user, rid)
                    if ok:
                        st.toast(f"Request #{rid} dispatched")
                        st.rerun()
                if ui.confirm_dialog(f"cancel_{rid}", "Cancel request", f"Cancel request #{rid}? Reserved units go back into stock.",
                                     confirm_label="Yes, cancel", danger=True):
                    ok, error, _ = attempt(cancel_request, user, rid, "cancelled from the open list")
                    if ok:
                        st.toast(f"Request #{rid} cancelled; units released")
                        st.rerun()
        st.divider()
    if error:
        ui.alert_banner(error, "danger")


with guard():
    tab_new, tab_open, tab_history = st.tabs(["New emergency", "Open requests", "History"])
    hospitals = get_all_hospitals()
    with tab_new:
        flow = _flow()
        ui.steps(STEPS, min(flow["step"], 3))
        if flow["step"] == 1:
            _step_need(flow, hospitals)
        elif flow["step"] == 2:
            _step_sources(flow, hospitals)
        elif flow["step"] == 3:
            _step_confirm(flow)
        else:
            _step_done(flow)
    with tab_open:
        _open_requests(user.role in (Role.SUPER_ADMIN, Role.HOSPITAL_ADMIN))
    with tab_history:
        scope = None if user.role is Role.SUPER_ADMIN else user.hospital_id
        closed = [r for r in get_blood_requests(scope) if r["status"] in ("RESOLVED", "CANCELLED")]
        ui.data_table(
            closed,
            [ui.Col("#", "id", align="right"), ui.Col("Patient", "patient_name"),
             ui.Col("Group", "blood_group", render=lambda v, r: ui.blood_group_badge(v)), ui.Col("Units", "units_needed", align="right"),
             ui.Col("Urgency", "urgency", render=lambda v, r: ui.status_pill(v)), ui.Col("Status", "status", render=lambda v, r: ui.status_pill(v)),
             ui.Col("Hospital", "hospital_name"), ui.Col("Requested", "created_at", render=lambda v, r: str(v)[:16].replace("T", " ")),
             ui.Col("Closed", "resolved_at", render=lambda v, r: str(v or "")[:16].replace("T", " "))],
            key="em_hist", empty_title="No closed requests yet", empty_body="Dispatched and cancelled requests are listed here.")
