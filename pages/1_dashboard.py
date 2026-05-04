import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import time

from utils.supabase_client import (
    get_dashboard_stats, get_blood_units, get_expiring_units,
    get_active_contracts, get_emergency_requests, get_hospitals,
    get_audit_logs, resolve_emergency
)
from utils.dsa_bridge import fefo_sort, get_hospital_graph
from utils.helpers import format_countdown, time_ago, get_status_color, pakistan_time
from utils.pdf_generator import generate_shift_report

if not st.session_state.get("logged_in"):
    st.warning("Please login from the main page.")
    st.stop()

from utils.sidebar import render_sidebar
render_sidebar()


role    = st.session_state.get("user_role")
hosp_id = st.session_state.get("hospital_id") if role != "super_admin" else None
email   = st.session_state.get("email","")

# ── MASTER CSS ──────────────────────────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'Outfit',sans-serif!important;}
.stApp{background:linear-gradient(-45deg,#0f0c29,#302b63,#24243e,#1a1a2e);background-size:400% 400%;animation:gradientBG 15s ease infinite;}
@keyframes gradientBG{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
footer,#MainMenu{visibility:hidden;} [data-testid='stSidebarNav'] { display: none !important; } [data-testid='stHeader'] { background: transparent !important; } [data-testid='stHeaderActionElements'] { display: none !important; }
.block-container{padding-top:1.5rem!important;}
.glass-card{background:rgba(20,20,35,0.7);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:24px;margin-bottom:16px;box-shadow:0 8px 32px rgba(0,0,0,0.4);transition:all 0.3s ease;}
.glass-card:hover{border-color:rgba(255,65,108,0.3);transform:translateY(-3px);box-shadow:0 12px 40px rgba(255,65,108,0.1);}
.metric-card{background:rgba(20,20,35,0.8);border:1px solid rgba(255,255,255,0.06);border-left:3px solid #ff416c;border-radius:12px;padding:18px 20px;transition:all 0.3s ease;}
.metric-value{font-size:2rem;font-weight:700;background:linear-gradient(135deg,#ff416c,#ff4b2b);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.1;}
.metric-label{font-size:0.72rem;color:#95A5A6;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:4px;}
.section-header{font-size:0.68rem;font-weight:600;color:#ff416c;text-transform:uppercase;letter-spacing:2px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid rgba(255,65,108,0.2);}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:0.7rem;font-weight:600;}
.badge-safe{background:rgba(0,210,170,0.15);color:#00D2AA;border:1px solid rgba(0,210,170,0.3);}
.badge-caution{background:rgba(255,179,71,0.15);color:#FFB347;border:1px solid rgba(255,179,71,0.3);}
.badge-critical{background:rgba(255,65,108,0.15);color:#ff416c;border:1px solid rgba(255,65,108,0.3);}
.live-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#00D2AA;animation:pulse-anim 2s infinite;margin-right:6px;}
.live-dot-red{display:inline-block;width:8px;height:8px;border-radius:50%;background:#ff416c;animation:pulse-red 1s infinite;margin-right:6px;}
@keyframes pulse-anim{0%,100%{box-shadow:0 0 0 0 rgba(0,210,170,0.4);}50%{box-shadow:0 0 0 8px rgba(0,210,170,0);}}
@keyframes pulse-red{0%,100%{box-shadow:0 0 0 0 rgba(255,65,108,0.4);}50%{box-shadow:0 0 0 8px rgba(255,65,108,0);}}
.alert-critical{background:linear-gradient(90deg,rgba(255,65,108,0.15),transparent);border-left:3px solid #ff416c;border-radius:0 8px 8px 0;padding:10px 16px;margin-bottom:8px;color:#ECF0F1;font-size:0.9rem;}
.alert-warning{background:linear-gradient(90deg,rgba(255,179,71,0.15),transparent);border-left:3px solid #FFB347;border-radius:0 8px 8px 0;padding:10px 16px;margin-bottom:8px;color:#ECF0F1;font-size:0.9rem;}
.data-table{width:100%;border-collapse:collapse;}
.data-table th{background:rgba(255,65,108,0.1);color:#ff416c;font-size:0.68rem;text-transform:uppercase;letter-spacing:1px;padding:10px 14px;text-align:left;border-bottom:1px solid rgba(255,65,108,0.2);}
.data-table td{padding:10px 14px;color:#ECF0F1;font-size:0.85rem;border-bottom:1px solid rgba(255,255,255,0.03);}
.data-table tr:hover td{background:rgba(255,65,108,0.04);}
.countdown{font-family:'Courier New',monospace;font-size:1.3rem;font-weight:700;letter-spacing:3px;}
.countdown-red{color:#ff416c;text-shadow:0 0 10px rgba(255,65,108,0.5);}
.countdown-amber{color:#FFB347;text-shadow:0 0 10px rgba(255,179,71,0.5);}
.countdown-green{color:#00D2AA;text-shadow:0 0 10px rgba(0,210,170,0.5);}
.stButton>button{background:linear-gradient(135deg,#ff416c,#ff4b2b)!important;color:white!important;border:none!important;border-radius:10px!important;font-weight:600!important;transition:all 0.3s ease!important;box-shadow:0 4px 15px rgba(255,65,108,0.3)!important;}
.stButton>button:hover{transform:translateY(-2px)!important;box-shadow:0 8px 25px rgba(255,65,108,0.5)!important;}
</style>""", unsafe_allow_html=True)

# ── PAGE HEADER ─────────────────────────────────
st.markdown(f"""<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
  <div>
    <h1 style="margin:0;font-size:2rem;color:white;">
      <span class="live-dot"></span> Command Center
    </h1>
    <p style="color:#95A5A6;margin:4px 0 0 0;">Real-time Blood Network — Lahore, Pakistan</p>
  </div>
  <div style="text-align:right;">
    <div style="color:#95A5A6;font-size:0.8rem;">{pakistan_time()}</div>
    <span class="badge badge-safe">LIVE</span>
  </div>
</div>""", unsafe_allow_html=True)

stats = get_dashboard_stats(hosp_id)

col1, col2 = st.columns([8, 2])
with col2:
    if st.button("📄 Generate Shift Report", use_container_width=True):
        pdf_bytes = generate_shift_report(stats)
        st.download_button(
            label="⬇ Download PDF",
            data=pdf_bytes,
            file_name=f"Shift_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

# ── ALERT BANNERS ───────────────────────────────
contracts = get_active_contracts()
if hosp_id:
    contracts = [c for c in contracts if c.get("lending_hospital_id")==hosp_id or c.get("borrowing_hospital_id")==hosp_id]

for c in contracts:
    hrs = c.get("hours_remaining", 99)
    if hrs < 2:
        st.markdown(f"""<div class='alert-critical'>
            <span class='live-dot-red'></span>
            <b>CONTRACT BREACH IMMINENT:</b> Ticket <b>{c.get('ticket_id')}</b> — return deadline in
            <b>{format_countdown(c.get('seconds_remaining',0))}</b>
        </div>""", unsafe_allow_html=True)

if stats.get("temp_alerts",0) > 0:
    st.markdown(f"""<div class='alert-warning'>
        <b>COLD CHAIN ALERT:</b> {stats['temp_alerts']} blood unit(s) exceeding safe storage temperature (>6°C).
    </div>""", unsafe_allow_html=True)

# ── KPI METRICS ─────────────────────────────────
c1,c2,c3,c4,c5,c6 = st.columns(6)
def metric_card(label, val, delta=""):
    return f"""<div class='metric-card'><div class='metric-label'>{label}</div>
    <div class='metric-value'>{val}</div>
    {'<div class="metric-delta">'+delta+'</div>' if delta else ''}</div>"""

c1.markdown(metric_card("Total Units",       stats.get("total_units",0),     "Available"),  unsafe_allow_html=True)
c2.markdown(metric_card("Expiring 3 Days",   stats.get("expiring_3_days",0), "Urgent"),     unsafe_allow_html=True)
c3.markdown(metric_card("Active Contracts",  stats.get("active_contracts",0),"In transit"), unsafe_allow_html=True)
c4.markdown(metric_card("Emergencies",       stats.get("live_emergencies",0),"Network wide"),unsafe_allow_html=True)
c5.markdown(metric_card("Temp Alerts",       stats.get("temp_alerts",0),     "Cold chain"),  unsafe_allow_html=True)
c6.markdown(metric_card("Hospitals Online",  stats.get("hospitals_online",0),"Active nodes"),unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── BLOOD GROUP GRID ────────────────────────────
st.markdown("<div class='section-header'>BLOOD GROUP STATUS</div>", unsafe_allow_html=True)
groups = ["O+","O-","A+","A-","B+","B-","AB+","AB-"]
units_by_group = stats.get("units_by_group",{})
cols = st.columns(4)
for i, g in enumerate(groups):
    count = units_by_group.get(g, 0)
    if count >= 20:
        status_c, badge_cls, badge_txt = "#00D2AA","badge-safe","GOOD"
    elif count >= 10:
        status_c, badge_cls, badge_txt = "#FFB347","badge-caution","LOW"
    else:
        status_c, badge_cls, badge_txt = "#ff416c","badge-critical","CRITICAL"
    fill = min(100, count * 5)
    with cols[i % 4]:
        st.markdown(f"""<div class='glass-card' style='padding:16px;text-align:center;'>
            <div style='font-size:1.6rem;font-weight:800;color:{status_c};'>{g}</div>
            <div style='font-size:2rem;font-weight:700;color:white;margin:4px 0;'>{count}</div>
            <span class='badge {badge_cls}'>{badge_txt}</span>
        </div>""", unsafe_allow_html=True)
        st.progress(fill)

st.markdown("<br>", unsafe_allow_html=True)

# ── ROW 3: EXPIRING UNITS + CONTRACT COUNTDOWN ──
r3a, r3b = st.columns([6,4])

with r3a:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>EXPIRING UNITS — FEFO ORDER</div>", unsafe_allow_html=True)
    expiring = get_expiring_units(days=7)
    if hosp_id:
        expiring = [u for u in expiring if u.get("hospital_id")==hosp_id]
    sorted_exp = fefo_sort(expiring) if expiring else []
    if sorted_exp:
        rows_html = ""
        for u in sorted_exp[:8]:
            d = u.get("days_to_expiry",99)
            row_color = "rgba(255,65,108,0.1)" if d<=2 else ("rgba(255,179,71,0.05)" if d<=5 else "rgba(0,210,170,0.03)")
            exp_badge = f"<span class='badge badge-critical'>{d}d</span>" if d<=2 else (f"<span class='badge badge-caution'>{d}d</span>" if d<=5 else f"<span class='badge badge-safe'>{d}d</span>")
            rows_html += f"""<tr style='background:{row_color};'>
                <td><code style='color:#ff416c;'>{u.get('unit_code','')}</code></td>
                <td><b>{u.get('blood_group','')}</b></td>
                <td>{u.get('component','')}</td>
                <td>{u.get('hospital_name','')}</td>
                <td>{u.get('storage_temperature','')}°C</td>
                <td>{u.get('expiry_date','')}</td>
                <td>{exp_badge}</td>
            </tr>"""
        st.markdown(f"""<table class='data-table'><thead><tr>
            <th>Unit ID</th><th>Group</th><th>Component</th>
            <th>Hospital</th><th>Temp</th><th>Expiry</th><th>Days</th>
        </tr></thead><tbody>{rows_html}</tbody></table>""", unsafe_allow_html=True)
        st.markdown("<p style='color:#95A5A6;font-size:0.72rem;margin-top:8px;'>DSA: Min-Heap — FEFO order. O(log n) insert, O(1) peek.</p>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='alert-warning' style='color:#00D2AA;border-left-color:#00D2AA;'>No units expiring within 7 days.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with r3b:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>ACTIVE CONTRACTS — LIVE COUNTDOWN</div>", unsafe_allow_html=True)
    display_contracts = contracts[:4]
    if display_contracts:
        for c in display_contracts:
            secs = c.get("seconds_remaining", 0)
            hrs  = c.get("hours_remaining", 99)
            cd_class = "countdown-red" if hrs < 6 else ("countdown-amber" if hrs < 12 else "countdown-green")
            border   = "#ff416c" if hrs < 6 else ("#FFB347" if hrs < 12 else "#00D2AA")
            st.markdown(f"""<div style='border:1px solid {border};border-radius:12px;
                padding:14px;margin-bottom:10px;background:rgba(0,0,0,0.2);'>
                <div style='display:flex;justify-content:space-between;align-items:center;'>
                    <div>
                        <code style='color:#ff416c;font-size:0.95rem;'>{c.get('ticket_id','')}</code><br>
                        <span style='color:#95A5A6;font-size:0.78rem;'>
                            {c.get('lending_hospital_name','')[:12]} → {c.get('borrowing_hospital_name','')[:12]}
                        </span>
                    </div>
                    <div class='countdown {cd_class}'>{format_countdown(secs)}</div>
                </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown("<p style='color:#00D2AA;'>No active contracts.</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── ROW 4: EMERGENCIES + AUDIT FEED ─────────────
r4a, r4b = st.columns([5,5])

with r4a:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>LIVE EMERGENCIES</div>", unsafe_allow_html=True)
    emgs = get_emergency_requests()
    pending_emgs = [e for e in emgs if e.get("status")=="pending"]
    if pending_emgs:
        for e in pending_emgs[:5]:
            lvl = e.get("urgency_level","")
            col = "#ff416c" if "1" in lvl else ("#FFB347" if "2" in lvl else "#3498DB")
            hosp_name = e.get("requesting_name","Unknown")
            st.markdown(f"""<div style='border-left:3px solid {col};background:rgba(0,0,0,0.2);
                padding:12px;border-radius:0 8px 8px 0;margin-bottom:8px;'>
                <div style='display:flex;justify-content:space-between;'>
                    <div>
                        <b style='color:white;'>{e.get('blood_group','')} {e.get('component','')}</b>
                        &nbsp;<span style='color:{col};font-size:0.75rem;'>{lvl[:7]}</span><br>
                        <span style='color:#95A5A6;font-size:0.8rem;'>{hosp_name} — {e.get('units_required',1)} units</span>
                    </div>
                    <span style='color:#95A5A6;font-size:0.75rem;'>{time_ago(e.get('created_at',''))}</span>
                </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown("<div style='color:#00D2AA;padding:10px;'>No active emergencies. Network clear.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with r4b:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>RECENT AUDIT ACTIVITY</div>", unsafe_allow_html=True)
    logs = get_audit_logs(limit=8, hospital_id=hosp_id)
    if logs:
        for log in logs:
            action = log.get("action","")
            actor  = log.get("actor_id","")
            ts     = time_ago(log.get("created_at",""))
            icon   = "🔴" if "BREACH" in action or "BLOCK" in action else ("🟡" if "WARN" in action else "🟢")
            st.markdown(f"""<div style='display:flex;justify-content:space-between;align-items:center;
                padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);'>
                <div>
                    <span style='font-size:0.75rem;'>{icon}</span>
                    <span style='color:#ECF0F1;font-size:0.85rem;margin-left:6px;'>{action}</span><br>
                    <span style='color:#95A5A6;font-size:0.72rem;margin-left:18px;'>{actor}</span>
                </div>
                <span style='color:#95A5A6;font-size:0.75rem;white-space:nowrap;'>{ts}</span>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No audit logs yet.")
    st.markdown("</div>", unsafe_allow_html=True)

# ── MAP ─────────────────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>HOSPITAL NETWORK MAP — LAHORE</div>", unsafe_allow_html=True)

all_hospitals = get_hospitals()
hosp_units    = {h["id"]: len(get_blood_units(h["id"])) for h in all_hospitals}
_, edges      = get_hospital_graph()

m = folium.Map(location=[31.52, 74.32], zoom_start=12, tiles="CartoDB dark_matter")

for h in all_hospitals:
    u_count = hosp_units.get(h["id"], 0)
    color   = "green" if u_count > 5 else ("orange" if u_count > 0 else "red")
    folium.CircleMarker(
        location=[h.get("lat",31.52), h.get("lng",74.32)],
        radius=12, color=color, fill=True, fill_opacity=0.8,
        popup=folium.Popup(f"<b>{h['name']}</b><br>Units: {u_count}<br>{h.get('address','')}", max_width=200),
        tooltip=h["name"]
    ).add_to(m)
    folium.Marker(
        location=[h.get("lat",31.52), h.get("lng",74.32)],
        icon=folium.DivIcon(html=f"""<div style='font-size:9px;color:white;white-space:nowrap;
            font-weight:600;text-shadow:1px 1px 2px black;margin-top:14px;'>{h['name'][:12]}</div>""")
    ).add_to(m)

# Draw hospital connections
hosp_map = {h["id"]: h for h in all_hospitals}
drawn = set()
for e in edges:
    key = tuple(sorted([e["from"], e["to"]]))
    if key in drawn:
        continue
    drawn.add(key)
    ha = hosp_map.get(e["from"])
    hb = hosp_map.get(e["to"])
    if ha and hb:
        folium.PolyLine(
            [[ha.get("lat",31.52), ha.get("lng",74.32)],
             [hb.get("lat",31.52), hb.get("lng",74.32)]],
            color="#ff416c", weight=1.5, opacity=0.4, dash_array="6 6",
            tooltip=f"{e.get('distance',0)} km"
        ).add_to(m)

st_folium(m, height=380, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# ── CHARTS ROW ──────────────────────────────────
ch1, ch2, ch3 = st.columns(3)

dark = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Outfit", color="white"), margin=dict(l=0,r=0,t=30,b=0))

with ch1:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>UNITS BY BLOOD GROUP</div>", unsafe_allow_html=True)
    bg_df = pd.DataFrame(list(units_by_group.items()), columns=["Group","Count"]) if units_by_group else pd.DataFrame()
    if not bg_df.empty:
        bg_df["color"] = bg_df["Count"].apply(lambda x: "#ff416c" if x<10 else ("#FFB347" if x<20 else "#00D2AA"))
        fig = px.bar(bg_df, x="Group", y="Count", color="Count",
                     color_continuous_scale=["#ff416c","#FFB347","#00D2AA"], text="Count")
        fig.update_traces(textposition="outside")
        fig.update_layout(**dark, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data")
    st.markdown("</div>", unsafe_allow_html=True)

with ch2:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>COMPONENT BREAKDOWN</div>", unsafe_allow_html=True)
    comp_data = stats.get("units_by_component",{})
    if comp_data:
        comp_df = pd.DataFrame(list(comp_data.items()), columns=["Component","Count"])
        fig2 = px.pie(comp_df, values="Count", names="Component", hole=0.6,
                      color_discrete_sequence=["#ff416c","#ff4b2b","#FFB347","#3498DB","#00D2AA"])
        fig2.update_layout(**dark)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No data")
    st.markdown("</div>", unsafe_allow_html=True)

with ch3:
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-header'>HOSPITAL COMPARISON</div>", unsafe_allow_html=True)
    if all_hospitals:
        hosp_df = pd.DataFrame([{"Hospital": h["name"][:10], "Units": hosp_units.get(h["id"],0)} for h in all_hospitals])
        fig3 = px.bar(hosp_df, x="Hospital", y="Units", color="Units",
                      color_continuous_scale=["#302b63","#ff416c"], text="Units")
        fig3.update_traces(textposition="outside")
        fig3.update_layout(**dark, coloraxis_showscale=False)
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No data")
    st.markdown("</div>", unsafe_allow_html=True)

# ── DEMAND FORECAST ─────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>BLOOD DEMAND FORECAST — RULE-BASED AI</div>", unsafe_allow_html=True)
today_wd = datetime.now().weekday()  # 0=Mon, 3=Thu, 4=Fri
fc1, fc2, fc3 = st.columns(3)

def forecast_card(period, demand, group, note, color):
    return f"""<div style='background:rgba(0,0,0,0.3);border:1px solid {color};border-radius:12px;
        padding:18px;text-align:center;'>
        <div style='color:#95A5A6;font-size:0.72rem;text-transform:uppercase;letter-spacing:1px;'>{period}</div>
        <div style='font-size:1.5rem;font-weight:700;color:{color};margin:8px 0;'>{demand}</div>
        <div style='color:white;font-size:0.85rem;'><b>{group}</b></div>
        <div style='color:#95A5A6;font-size:0.75rem;margin-top:6px;'>{note}</div>
    </div>"""

tonight_demand = "HIGH" if today_wd in [3,4] else "NORMAL"
tonight_group  = "O+, A+" if today_wd in [3,4] else "All groups"
weekend_demand = "ELEVATED" if today_wd in [4,5] else "STANDARD"
tonight_color  = "#ff416c" if tonight_demand=="HIGH" else "#00D2AA"
weekend_color  = "#FFB347" if weekend_demand=="ELEVATED" else "#00D2AA"

fc1.markdown(forecast_card("Tonight",  tonight_demand, tonight_group, "Pre-weekend surgical load", tonight_color), unsafe_allow_html=True)
fc2.markdown(forecast_card("Tomorrow", "MODERATE", "B+, O-", "Elective procedures", "#FFB347"), unsafe_allow_html=True)
fc3.markdown(forecast_card("Weekend",  weekend_demand, "O+ universal", "Emergency trauma cases", weekend_color), unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
