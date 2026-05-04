import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import time
from datetime import datetime

from utils.supabase_client import (
    get_emergency_requests, create_emergency_request,
    get_hospitals, resolve_emergency, add_patient, add_audit_log
)
from utils.dsa_bridge import dijkstra, bfs_backup, get_hospital_graph, screen_donor
from utils.helpers import time_ago

if not st.session_state.get("logged_in"):
    st.warning("Please login from the main page.")
    st.stop()

from utils.sidebar import render_sidebar
render_sidebar()


role    = st.session_state.get("user_role")
hosp_id = st.session_state.get("hospital_id") if role != "super_admin" else None

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'Outfit',sans-serif!important;}
.stApp{background:linear-gradient(-45deg,#0f0c29,#302b63,#24243e,#1a1a2e);background-size:400% 400%;animation:gradientBG 15s ease infinite;}
@keyframes gradientBG{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
footer,#MainMenu{visibility:hidden;} [data-testid='stSidebarNav'] { display: none !important; } [data-testid='stHeader'] { background: transparent !important; } [data-testid='stHeaderActionElements'] { display: none !important; }
.block-container{padding-top:1.5rem!important;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0D0D1A 0%,#1C1C2E 100%)!important;border-right:1px solid rgba(255,65,108,0.2);}
[data-testid="stSidebar"] *{color:#ECF0F1!important;}
.glass-card{background:rgba(20,20,35,0.7);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:24px;margin-bottom:16px;box-shadow:0 8px 32px rgba(0,0,0,0.4);transition:all 0.3s ease;}
.section-header{font-size:0.68rem;font-weight:600;color:#ff416c;text-transform:uppercase;letter-spacing:2px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid rgba(255,65,108,0.2);}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:0.7rem;font-weight:600;}
.stTextInput>div>div>input,.stSelectbox>div>div>div,.stNumberInput>div>div>input{background:rgba(0,0,0,0.3)!important;border:1px solid rgba(255,255,255,0.1)!important;color:white!important;border-radius:10px!important;}
.stButton>button{background:linear-gradient(135deg,#ff416c,#ff4b2b)!important;color:white!important;border:none!important;border-radius:10px!important;font-weight:600!important;transition:all 0.3s ease!important;box-shadow:0 4px 15px rgba(255,65,108,0.3)!important;}
.stButton>button:hover{transform:translateY(-2px)!important;box-shadow:0 8px 25px rgba(255,65,108,0.5)!important;}
.data-table{width:100%;border-collapse:collapse;}
.data-table th{background:rgba(255,65,108,0.1);color:#ff416c;font-size:0.68rem;text-transform:uppercase;letter-spacing:1px;padding:10px 14px;text-align:left;border-bottom:1px solid rgba(255,65,108,0.2);}
.data-table td{padding:10px 14px;color:#ECF0F1;font-size:0.85rem;border-bottom:1px solid rgba(255,255,255,0.03);}
</style>""", unsafe_allow_html=True)

st.markdown("<h1 style='color:white;'><span style='color:#ff416c;'>🚨</span> Emergency Blood Request</h1>", unsafe_allow_html=True)

if "dijkstra_result" not in st.session_state:
    st.session_state.dijkstra_result = None

# ── PATIENT FORM ────────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>PATIENT EMERGENCY ADMISSION</div>", unsafe_allow_html=True)
with st.form("emergency_form"):
    c1, c2 = st.columns(2)
    with c1:
        fname  = st.text_input("Full Name *")
        faname = st.text_input("Father/Husband Name *")
        cnic   = st.text_input("CNIC (Optional)")
        age    = st.number_input("Age *", min_value=0, max_value=120, value=30)
        gender = st.selectbox("Gender *", ["Male", "Female", "Other"])
        ward   = st.text_input("Ward *", "Emergency")
        bed    = st.text_input("Bed *", "ER-1")
        opd    = st.text_input("OPD/MRN Number *")
    with c2:
        bg     = st.selectbox("Blood Group Needed *", ["A+","A-","B+","B-","O+","O-","AB+","AB-"])
        comp   = st.selectbox("Component *", ["Whole Blood", "RBC", "Platelets", "Plasma", "FFP"])
        units  = st.number_input("Units Needed *", min_value=1, max_value=10, value=2)
        diag   = st.text_input("Diagnosis *")
        prio   = st.selectbox("Urgency Level", ["Level 1 - Critical (Immediate)", "Level 2 - Urgent (1-2 Hours)", "Level 3 - Standard (24 Hours)"])
        req_type = st.selectbox("Request Type", ["Transfusion", "Surgical Backup"])
        doctor = st.text_input("Attending Doctor *")

    submitted = st.form_submit_button("🚨 FIND BLOOD NOW", use_container_width=True)

if submitted:
    if not fname or not diag or not doctor or not hosp_id:
        st.error("Please fill all required fields and ensure you are assigned to a hospital.")
    else:
        patient_data = {
            "hospital_id": hosp_id, "cnic": cnic, "full_name": fname,
            "father_name": faname, "age": age, "gender": gender,
            "blood_group": bg, "mrn": opd, "ward": ward, "bed": bed,
            "opd_number": opd, "diagnosis": diag
        }
        pid = add_patient(patient_data)
        
        with st.spinner("Executing Dijkstra's Algorithm for Shortest Path Network Routing..."):
            hosp_nodes, edges = get_hospital_graph()
            # Mock available hospitals for demo
            avail = [h["id"] for h in hosp_nodes if h["id"] != hosp_id]
            res = dijkstra(hosp_nodes, edges, hosp_id, bg, avail)
            time.sleep(1) # Dramatic pause for UI
            
            backups = bfs_backup(hosp_nodes, edges, hosp_id, avail)
            res["backups"] = backups
            st.session_state.dijkstra_result = res
            
            req_data = {
                "requesting_hospital_id": hosp_id,
                "target_hospital_id": res.get("best_hospital_id", hosp_id),
                "blood_group": bg,
                "component": comp,
                "units_required": units,
                "urgency_level": prio,
                "status": "pending"
            }
            eid = create_emergency_request(req_data)
            add_audit_log("EMERGENCY_REQUEST", st.session_state["email"], hosp_id, "emergency", eid, req_data)
        
st.markdown("</div>", unsafe_allow_html=True)

# ── RESULTS & MAP ───────────────────────────────
if st.session_state.dijkstra_result:
    res = st.session_state.dijkstra_result
    st.markdown("<div class='glass-card' style='border-color:#00D2AA;'>", unsafe_allow_html=True)
    st.markdown("<h3 style='color:#00D2AA;margin-top:0;'>✓ Optimal Route Established</h3>", unsafe_allow_html=True)
    
    c1, c2 = st.columns([3, 7])
    with c1:
        if "error" in res:
            st.error(res["error"])
        else:
            hospitals = get_hospitals()
            h_map = {h["id"]: h["name"] for h in hospitals}
            best_name = h_map.get(res.get("best_hospital_id"), "Unknown")
            dist = res.get("distance", 0)
            st.markdown(f"**Target Hospital:** {best_name}")
            st.markdown(f"**Distance:** {dist} km")
            
            path_names = [h_map.get(i, i) for i in res.get("path", [])]
            st.markdown("**Routing:**")
            for p in path_names:
                st.markdown(f"<span class='badge' style='background:#3498DB;margin-bottom:4px;'>{p}</span>", unsafe_allow_html=True)
            
            st.markdown("<br>**Backup Options (BFS):**", unsafe_allow_html=True)
            for b in res.get("backups", [])[:2]:
                st.markdown(f"• {h_map.get(b, b)}")

        st.info("Dijkstra: O((V+E) log V)\nBFS Backup: O(V+E)\nNetwork: 4 nodes, 6 edges")
        
    with c2:
        hosp_nodes, edges = get_hospital_graph()
        m = folium.Map(location=[31.52, 74.32], zoom_start=12, tiles="CartoDB dark_matter")
        
        node_dict = {n["id"]: n for n in hosp_nodes}
        for n in hosp_nodes:
            folium.CircleMarker(
                location=[n["lat"], n["lng"]], radius=8,
                color="#3498DB", fill=True, popup=n["name"]
            ).add_to(m)
        
        path_ids = res.get("path", [])
        if len(path_ids) >= 2:
            path_coords = []
            for pid in path_ids:
                if pid in node_dict:
                    path_coords.append([node_dict[pid]["lat"], node_dict[pid]["lng"]])
            folium.PolyLine(path_coords, color="#ff416c", weight=3, opacity=0.8).add_to(m)
            
        st_folium(m, height=300, use_container_width=True)
        
    st.markdown("</div>", unsafe_allow_html=True)

# ── ACTIVE EMERGENCIES ──────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>ACTIVE NETWORK EMERGENCIES</div>", unsafe_allow_html=True)

emgs = get_emergency_requests()
pending = [e for e in emgs if e.get("status") == "pending"]

if pending:
    rows = ""
    for e in pending:
        req_name = e.get("requesting_name", "Unknown")
        lvl = e.get("urgency_level", "")
        lvl_html = f"<span style='color:#ff416c;'>{lvl}</span>" if "1" in lvl else f"<span style='color:#FFB347;'>{lvl}</span>"
        rows += f"""<tr>
            <td>{req_name}</td>
            <td><b>{e.get('blood_group')}</b> {e.get('component')} ({e.get('units_required')} units)</td>
            <td>{lvl_html}</td>
            <td>{time_ago(e.get('created_at',''))}</td>
            <td><span class='badge' style='background:rgba(255,179,71,0.2);color:#FFB347;'>Pending</span></td>
        </tr>"""
    st.markdown(f"<table class='data-table'><thead><tr><th>Requesting Hospital</th><th>Requirement</th><th>Priority</th><th>Time</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>", unsafe_allow_html=True)
else:
    st.markdown("<div style='color:#00D2AA;'>No active emergencies network-wide. ✓</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
