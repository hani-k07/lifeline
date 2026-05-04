import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from utils.supabase_client import (
    get_blood_units, add_blood_unit, get_donors, get_hospitals,
    update_unit_status, add_audit_log
)
from utils.dsa_bridge import fefo_sort
from utils.helpers import get_days_to_expiry, get_status_color

if not st.session_state.get("logged_in"):
    st.warning("Please login from the main page.")
    st.stop()

from utils.sidebar import render_sidebar
render_sidebar()


role    = st.session_state.get("user_role")
hosp_id = st.session_state.get("hospital_id") if role != "super_admin" else None

# ── MASTER CSS ──────────────────────────────────
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
.glass-card:hover{border-color:rgba(255,65,108,0.3);transform:translateY(-3px);box-shadow:0 12px 40px rgba(255,65,108,0.1);}
.metric-card{background:rgba(20,20,35,0.8);border:1px solid rgba(255,255,255,0.06);border-left:3px solid #ff416c;border-radius:12px;padding:18px 20px;transition:all 0.3s ease;}
.metric-card:hover{border-left-color:#ff4b2b;box-shadow:0 0 20px rgba(255,65,108,0.15);}
.metric-value{font-size:2rem;font-weight:700;background:linear-gradient(135deg,#ff416c,#ff4b2b);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.1;}
.metric-label{font-size:0.72rem;color:#95A5A6;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:4px;}
.section-header{font-size:0.68rem;font-weight:600;color:#ff416c;text-transform:uppercase;letter-spacing:2px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid rgba(255,65,108,0.2);}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:0.7rem;font-weight:600;}
.badge-safe{background:rgba(0,210,170,0.15);color:#00D2AA;border:1px solid rgba(0,210,170,0.3);}
.badge-caution{background:rgba(255,179,71,0.15);color:#FFB347;border:1px solid rgba(255,179,71,0.3);}
.badge-critical{background:rgba(255,65,108,0.15);color:#ff416c;border:1px solid rgba(255,65,108,0.3);}
.alert-warning{background:linear-gradient(90deg,rgba(255,179,71,0.15),transparent);border-left:3px solid #FFB347;border-radius:0 8px 8px 0;padding:10px 16px;margin-bottom:8px;color:#ECF0F1;font-size:0.9rem;}
.stTextInput>div>div>input,.stSelectbox>div>div>div,.stNumberInput>div>div>input,.stDateInput>div>div>input{background:rgba(0,0,0,0.3)!important;border:1px solid rgba(255,255,255,0.1)!important;color:white!important;border-radius:10px!important;}
.stTextInput>div>div>input:focus{border-color:#ff416c!important;box-shadow:0 0 12px rgba(255,65,108,0.25)!important;}
.stButton>button{background:linear-gradient(135deg,#ff416c,#ff4b2b)!important;color:white!important;border:none!important;border-radius:10px!important;font-weight:600!important;transition:all 0.3s ease!important;box-shadow:0 4px 15px rgba(255,65,108,0.3)!important;}
.stButton>button:hover{transform:translateY(-2px)!important;box-shadow:0 8px 25px rgba(255,65,108,0.5)!important;}
.data-table{width:100%;border-collapse:collapse;}
.data-table th{background:rgba(255,65,108,0.1);color:#ff416c;font-size:0.68rem;text-transform:uppercase;letter-spacing:1px;padding:10px 14px;text-align:left;border-bottom:1px solid rgba(255,65,108,0.2);}
.data-table td{padding:10px 14px;color:#ECF0F1;font-size:0.85rem;border-bottom:1px solid rgba(255,255,255,0.03);}
.data-table tr:hover td{background:rgba(255,65,108,0.04);}
</style>""", unsafe_allow_html=True)

st.markdown("<h1 style='color:white;'><span style='color:#ff416c;'>🩸</span> Blood Inventory Management</h1>", unsafe_allow_html=True)

all_units = get_blood_units(None)
if role != "super_admin":
    units = [u for u in all_units if u.get("hospital_id") == hosp_id]
else:
    units = all_units

# ── QUICK STATS ─────────────────────────────────
avail_count = len(units)
reserved    = sum(1 for u in units if u.get("status") == "reserved")
expiring    = sum(1 for u in units if u.get("days_to_expiry", 99) <= 5)
temp_alerts = sum(1 for u in units if u.get("storage_temperature", 4) > 6.0)

c1, c2, c3, c4 = st.columns(4)
def stat_card(label, val, color):
    return f"<div class='metric-card' style='border-left-color:{color};'><div class='metric-label'>{label}</div><div class='metric-value'>{val}</div></div>"
c1.markdown(stat_card("Available", avail_count, "#00D2AA"), unsafe_allow_html=True)
c2.markdown(stat_card("Reserved", reserved, "#3498DB"), unsafe_allow_html=True)
c3.markdown(stat_card("Expiring ≤ 5 Days", expiring, "#FFB347"), unsafe_allow_html=True)
c4.markdown(stat_card("Temp Alerts", temp_alerts, "#ff416c"), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── ADD BLOOD UNIT ──────────────────────────────
with st.expander("➕ ADD NEW BLOOD UNIT"):
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    with st.form("add_unit_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            bg = st.selectbox("Blood Group", ["A+","A-","B+","B-","O+","O-","AB+","AB-"])
            comp = st.selectbox("Component", ["Whole Blood", "RBC", "Platelets", "Plasma", "FFP"])
            donors = get_donors()
            donor_opts = {f"{d['full_name']} ({d['blood_group']})": d["id"] for d in donors}
            donor_sel = st.selectbox("Donor", list(donor_opts.keys()))
            vol = st.number_input("Volume (ml)", value=450)
            
        with col2:
            hospitals = get_hospitals()
            if role == "super_admin":
                hosp_opts = {h["name"]: h["id"] for h in hospitals}
                hosp_sel = st.selectbox("Hospital", list(hosp_opts.keys()))
            else:
                hosp_sel = next(h["name"] for h in hospitals if h["id"] == hosp_id)
                st.text_input("Hospital", hosp_sel, disabled=True)
            
            coll_date = st.date_input("Collection Date")
            exp_date = st.date_input("Expiry Date")
            temp = st.number_input("Storage Temp (°C)", value=4.0, step=0.1)

        if st.form_submit_button("REGISTER UNIT IN INVENTORY", use_container_width=True):
            hid = hosp_opts[hosp_sel] if role == "super_admin" else hosp_id
            new_unit = {
                "hospital_id": hid,
                "donor_id": donor_opts[donor_sel],
                "blood_group": bg,
                "component": comp,
                "volume_ml": vol,
                "collection_date": str(coll_date),
                "expiry_date": str(exp_date),
                "storage_temperature": temp
            }
            if add_blood_unit(new_unit):
                add_audit_log("UNIT_ADDED", st.session_state["email"], hid, "blood_unit", "NEW", new_unit)
                st.success("✓ Unit successfully added to inventory.")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Failed to add unit.")
    st.markdown("</div>", unsafe_allow_html=True)

# ── COLD CHAIN ALERTS ───────────────────────────
if temp_alerts > 0:
    for u in units:
        if u.get("storage_temperature", 4) > 6.0:
            st.markdown(f"""<div class='alert-warning'>
                <span class='live-dot-red'></span> <b>COLD CHAIN BREACH:</b> Unit {u.get('unit_code','')} ({u.get('blood_group','')}) at {u.get('storage_temperature')}°C. Move immediately!
            </div>""", unsafe_allow_html=True)

# ── FEFO QUEUE & FILTERS ────────────────────────
f1, f2 = st.columns([3, 7])

with f1:
    st.markdown("<div class='glass-card' style='height:100%;'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>⏳ FEFO QUEUE — MIN-HEAP TOP 5</div>", unsafe_allow_html=True)
    sorted_units = fefo_sort(units)
    if sorted_units:
        for i, u in enumerate(sorted_units[:5]):
            d = u.get("days_to_expiry", 99)
            color = "#ff416c" if i==0 else ("#FFB347" if d<=5 else "#00D2AA")
            st.markdown(f"""<div style='background:rgba(0,0,0,0.3);border-left:3px solid {color};
                padding:10px;margin-bottom:8px;border-radius:6px;'>
                <div style='display:flex;justify-content:space-between;'>
                    <b style='color:white;'>{u.get('blood_group','')} {u.get('component','')}</b>
                    <span style='color:{color};font-size:0.8rem;'>{d} days left</span>
                </div>
                <div style='color:#95A5A6;font-size:0.7rem;font-family:monospace;'>{u.get('unit_code','')}</div>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No units available.")
    st.markdown("<p style='color:#95A5A6;font-size:0.7rem;margin-top:10px;'>DSA: Min-Heap ensures soonest-expiring unit is selected first. O(1) access.</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with f2:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>INVENTORY FILTERS</div>", unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1: f_bg = st.multiselect("Blood Group", ["A+","A-","B+","B-","O+","O-","AB+","AB-"])
    with fc2: f_comp = st.multiselect("Component", ["Whole Blood", "RBC", "Platelets", "Plasma", "FFP"])
    with fc3: 
        if role == "super_admin":
            hospitals = get_hospitals()
            f_hosp = st.selectbox("Hospital", ["All"] + [h["name"] for h in hospitals])
        else:
            f_hosp = "All"
    with fc4: f_alert = st.checkbox("Temp Alerts Only")

    # Apply filters
    filtered = sorted_units
    if f_bg: filtered = [u for u in filtered if u.get("blood_group") in f_bg]
    if f_comp: filtered = [u for u in filtered if u.get("component") in f_comp]
    if f_hosp != "All": filtered = [u for u in filtered if u.get("hospital_name") == f_hosp]
    if f_alert: filtered = [u for u in filtered if u.get("storage_temperature", 4) > 6.0]

    st.markdown("<div class='section-header' style='margin-top:20px;'>MAIN INVENTORY</div>", unsafe_allow_html=True)
    
    if filtered:
        rows = ""
        for u in filtered:
            d = u.get("days_to_expiry", 99)
            row_bg = "rgba(255,65,108,0.1)" if d<=2 else ("rgba(255,179,71,0.05)" if d<=5 else "transparent")
            badge = f"<span class='badge badge-critical'>{d}d</span>" if d<=2 else (f"<span class='badge badge-caution'>{d}d</span>" if d<=5 else f"<span class='badge badge-safe'>{d}d</span>")
            temp = u.get("storage_temperature", 4)
            t_str = f"⚠️ {temp}°C" if temp > 6.0 else f"{temp}°C"
            rows += f"""<tr style='background:{row_bg};'>
                <td><code style='color:#3498DB;'>{u.get('unit_code','')}</code></td>
                <td><b>{u.get('blood_group','')}</b></td>
                <td>{u.get('component','')}</td>
                <td>{u.get('hospital_name','')}</td>
                <td style='color:{"#ff416c" if temp>6.0 else "#ECF0F1"}'>{t_str}</td>
                <td>{badge}</td>
                <td>
                    <button style='background:transparent;border:1px solid #3498DB;color:#3498DB;padding:2px 8px;border-radius:4px;cursor:pointer;'>Reserve</button>
                </td>
            </tr>"""
        st.markdown(f"""<div style='max-height:400px;overflow-y:auto;'><table class='data-table'>
            <thead><tr><th>Unit ID</th><th>Group</th><th>Component</th><th>Hospital</th><th>Temp</th><th>Expiry</th><th>Action</th></tr></thead>
            <tbody>{rows}</tbody></table></div>""", unsafe_allow_html=True)
    else:
        st.info("No units match the selected filters.")
    st.markdown("</div>", unsafe_allow_html=True)

# ── CHARTS ──────────────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
t1, t2 = st.tabs(["Inventory Distribution", "Expiry Scatter"])
dark = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Outfit", color="white"), margin=dict(l=0,r=0,t=30,b=0))

if filtered:
    df = pd.DataFrame(filtered)
    with t1:
        bg_counts = df["blood_group"].value_counts().reset_index()
        bg_counts.columns = ["Blood Group", "Count"]
        fig1 = px.bar(bg_counts, x="Blood Group", y="Count", color="Count", color_continuous_scale=["#302b63","#ff416c"])
        fig1.update_layout(**dark, coloraxis_showscale=False)
        st.plotly_chart(fig1, use_container_width=True)
    
    with t2:
        fig2 = px.scatter(df, x="collection_date", y="expiry_date", color="days_to_expiry", hover_data=["blood_group", "component"],
                          color_continuous_scale=["#ff416c","#FFB347","#00D2AA"])
        fig2.update_layout(**dark)
        st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("No data for charts.")
st.markdown("</div>", unsafe_allow_html=True)
