# pages/4_exchange.py
"""Blood Exchange Network — LIFELINE v6.0"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Exchange — LIFELINE", layout="wide")

from utils.styles import (
    inject_all_styles, get_theme, section_header, alert_banner,
    blood_badge, status_pill, styled_table,
)
from lifeline.auth.roles import Role
from utils.sidebar import render_sidebar
from utils.database import (
    get_all_hospitals, get_exchanges, add_exchange,
    get_blood_units, add_audit_log,
)
from dsa_engine import build_hospital_graph, BLOOD_GROUPS

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
    <h1 style="font-family:'Syne',sans-serif;font-size:1.6rem;margin:0">Blood Exchange</h1>
    <p style="color:var(--text-secondary);font-size:0.82rem;margin:4px 0 0">
        Inter-hospital blood transfers powered by Dijkstra graph routing
    </p>
</div>""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["Find & Request Exchange", "Exchange History"])

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
            graph = build_hospital_graph(hospitals)
            all_inv = get_blood_units()
            nearest = graph.nearest_hospitals_with_blood(src_hosp["id"], blood_grp, all_inv)

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

        for r in results[:5]:
            with st.container():
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                eta = round(r["distance_km"] / 5 * 15, 0)
                
                c1.markdown(f"<div style='font-size:0.95rem;font-weight:600;'>{r['hospital_name']}</div>", unsafe_allow_html=True)
                c2.markdown(f"<span style='font-family:\"JetBrains Mono\",monospace;font-size:0.85rem;'>{r['distance_km']} km</span>", unsafe_allow_html=True)
                c3.markdown(f"<span style='font-family:\"JetBrains Mono\",monospace;font-size:0.85rem;'>{r['units_available']} units</span>", unsafe_allow_html=True)
                c4.markdown(f"<span style='font-family:\"JetBrains Mono\",monospace;font-size:0.85rem;'>~{int(eta)} min ETA</span>", unsafe_allow_html=True)

                # Path display
                if r.get("path"):
                    path_names = []
                    hosp_id_to_name = {h["id"]: h["name"] for h in hospitals}
                    for pid in r["path"]:
                        path_names.append(hosp_id_to_name.get(pid, str(pid)))
                    st.caption(f"Route: {' -> '.join(path_names)}")

                if st.button(f"Request Exchange from {r['hospital_name']}", key=f"req_{r['hospital_id']}"):
                    ok = add_exchange(r["hospital_id"], src["id"], bg, min(needed, r["units_available"]))
                    if ok:
                        add_audit_log("EXCHANGE_REQUEST", f"Exchange request: {bg} from {r['hospital_name']} to {src['name']}", _uid)
                        alert_banner(f"Exchange request sent to {r['hospital_name']}", "success")
                        del st.session_state["exchange_results"]
                        st.rerun()
                st.divider()

with tab2:
    exchanges = get_exchanges(_hosp_id if _role != Role.SUPER_ADMIN else None)
    if not exchanges:
        alert_banner("No exchange transactions recorded yet.", "info")
    else:
        history_rows = []
        for ex in exchanges:
            history_rows.append({
                "From": ex.get("from_name", "—"),
                "To": ex.get("to_name", "—"),
                "Blood Group": blood_badge(ex.get("blood_group", "?")),
                "Units": ex.get("units", 0),
                "Status": status_pill(ex.get("status", "PENDING")),
                "Created": ex.get("created_at", "")[:16].replace("T", " ") if ex.get("created_at") else "—"
            })
        df_show = pd.DataFrame(history_rows)
        styled_table(df_show)

