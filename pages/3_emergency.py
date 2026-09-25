# pages/3_emergency.py
"""Emergency Blood Requests — LIFELINE v6.0"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Emergency — LIFELINE", layout="wide")

from utils.styles import (
    inject_all_styles, get_theme, section_header, alert_banner,
    blood_badge, status_pill, styled_table,
)
from utils.sidebar import render_sidebar
from utils.database import (
    get_all_hospitals, get_blood_requests, add_blood_request,
    resolve_blood_request, get_blood_summary, add_audit_log,
)
from dsa_engine import TriageQueue, build_hospital_graph, BLOOD_GROUPS

if not st.session_state.get("logged_in"):
    st.switch_page("app.py")
    st.stop()

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

# ── Tab 1: Queue ──
with tab1:
    requests = get_blood_requests(_hosp_id if _role != "admin" else None)
    pending = [r for r in requests if r.get("status") == "PENDING"]
    resolved = [r for r in requests if r.get("status") == "RESOLVED"]

    # Build triage queue
    tq = TriageQueue()
    priority_map = {"CRITICAL": 1, "URGENT": 2, "ROUTINE": 3}
    for r in pending:
        p = priority_map.get(r.get("urgency", "ROUTINE"), 3)
        tq.push(p, r)

    section_header(f"Active Queue", f"{len(pending)} pending requests")

    if not pending:
        alert_banner("No pending emergency requests in the queue.", "success")
    else:
        for req in tq.all_sorted():
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1.5, 1])
                ug = req.get("urgency", "ROUTINE")
                bg = req.get("blood_group", "?")
                pt = req.get("patient_name", "Unknown")
                ts = str(req.get("created_at", ""))[:16].replace("T", " ")
                hosp = req.get("hospital_name", "—")
                
                c1.markdown(f"<div style='font-size:0.9rem;font-weight:600;color:var(--text-primary)'>{pt}</div><div style='font-size:0.75rem;color:var(--text-secondary)'>{req.get('patient_condition','N/A')}</div>", unsafe_allow_html=True)
                c2.markdown(status_pill(ug), unsafe_allow_html=True)
                c3.markdown(f"{blood_badge(bg)} <span style='font-family:\"JetBrains Mono\",monospace;font-size:0.85rem'>× {req.get('units_needed','?')}u</span>", unsafe_allow_html=True)
                c4.markdown(f"<div style='font-size:0.75rem;color:var(--text-secondary)'>{hosp}</div><div style='font-size:0.68rem;color:var(--text-muted)'>{ts}</div>", unsafe_allow_html=True)
                
                if _role in ("admin", "hospital"):
                    if c5.button("Resolve", key=f"res_{req['id']}"):
                        resolve_blood_request(req["id"])
                        add_audit_log("EMERGENCY_RESOLVED", f"Resolved request for {pt} — {bg}", _uid)
                        st.rerun()
                st.divider()

    if resolved:
        with st.expander(f"Resolved Requests ({len(resolved)})"):
            resolved_rows = []
            for r in resolved:
                resolved_rows.append({
                    "Patient": r["patient_name"],
                    "Blood Group": blood_badge(r["blood_group"]),
                    "Units": r["units_needed"],
                    "Urgency": status_pill(r["urgency"]),
                    "Requested": r["created_at"][:16].replace("T", " ") if r.get("created_at") else "—",
                    "Resolved": r["resolved_at"][:16].replace("T", " ") if r.get("resolved_at") else "—"
                })
            styled_table(pd.DataFrame(resolved_rows))

# ── Tab 2: New Request ──
with tab2:
    section_header("Submit Emergency Blood Request")
    
    error_msg = None
    success_msg = None

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

        if _role == "admin":
            hospitals = get_all_hospitals()
            hosp_map = {h["name"]: h["id"] for h in hospitals}
            sel_h = st.selectbox("Requesting Hospital", list(hosp_map.keys()))
            req_hosp_id = hosp_map[sel_h]
        else:
            req_hosp_id = _hosp_id

        submitted = st.form_submit_button("Submit Emergency Request", use_container_width=True)
        if submitted:
            if not patient_name:
                error_msg = "Patient name is required."
            else:
                ok = add_blood_request(req_hosp_id, bg, units, urgency, patient_name, condition)
                if ok:
                    add_audit_log("EMERGENCY_REQUEST", f"Emergency {urgency} request for {units}u {bg} — {patient_name}", _uid)
                    success_msg = f"{urgency} request submitted for {units} units of {bg}"
                else:
                    error_msg = "Failed to submit emergency request."

    if success_msg:
        alert_banner(success_msg, "success")
        st.rerun()
    elif error_msg:
        alert_banner(error_msg, "danger")

# ── Tab 3: Find Blood (Dijkstra) ──
with tab3:
    section_header("Find Blood via Network Graph (Dijkstra)")
    hospitals = get_all_hospitals()

    col1, col2, col3 = st.columns(3)
    with col1:
        hosp_names = [h["name"] for h in hospitals]
        src_name = st.selectbox("Your Hospital", hosp_names, index=0)
    with col2:
        need_bg = st.selectbox("Blood Group Needed", BLOOD_GROUPS, key="find_bg")
    with col3:
        need_units = st.number_input("Units Needed", min_value=1, max_value=50, value=3)

    find_clicked = st.button("Find Nearest Blood Source", use_container_width=True)
    if find_clicked:
        from utils.database import get_blood_units as get_bu
        src_hosp = next((h for h in hospitals if h["name"] == src_name), None)
        if src_hosp:
            graph = build_hospital_graph(hospitals)
            all_inv = get_bu()
            nearest = graph.nearest_hospitals_with_blood(src_hosp["id"], need_bg, all_inv)

            if nearest:
                alert_banner(f"Found {len(nearest)} hospitals with {need_bg} blood!", "success")
                rows = []
                for r in nearest[:6]:
                    eta = round(r["distance_km"] / 5 * 15, 0)  # ~15min per 5km
                    rows.append({
                        "Hospital": r["hospital_name"],
                        "Distance": f"{r['distance_km']} km",
                        "Stock": f"{r['units_available']} units",
                        "ETA": f"~{int(eta)} min"
                    })
                styled_table(pd.DataFrame(rows))
            else:
                alert_banner(f"No hospitals in the network have {need_bg} blood available.", "danger")

