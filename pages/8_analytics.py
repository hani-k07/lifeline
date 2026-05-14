import streamlit as st
import pandas as pd
import plotly.express as px
import time

from utils.supabase_client import get_dashboard_stats, get_blood_units, get_hospitals

if not st.session_state.get("logged_in"):
    st.warning("Please login from the main page.")
    st.stop()

# Access Control
role = st.session_state.get("user_role", "staff")
if role not in ["super_admin", "hospital_admin"]:
    st.markdown("""
    <style>
    .glass-card {
        background: rgba(20,20,35,0.7);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 16px;
        text-align: center;
    }
    </style>
    <div class='glass-card' style='border-color:rgba(255,65,108,0.4);'>
        <h2 style='color:white;'>🚫 Access Denied</h2>
        <p style='color:#95A5A6;'>You do not have permission to view this page. Hospital Admin or Super Admin only.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

from utils.sidebar import render_sidebar
render_sidebar()


from utils.styles import get_glass_css
st.markdown(get_glass_css(), unsafe_allow_html=True)

st.markdown("<h1 style='color:white;'><span style='color:#3498DB;'>📈</span> Analytics & Intelligence</h1>", unsafe_allow_html=True)

# ── KPI CARDS ───────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)
def stat_card(label, val, color):
    return f"<div class='metric-card' style='border-left-color:{color};'><div class='metric-label'>{label}</div><div class='metric-value'>{val}</div></div>"
c1.markdown(stat_card("Wastage Rate", "1.2%", "#00D2AA"), unsafe_allow_html=True)
c2.markdown(stat_card("Avg Response", "14 min", "#3498DB"), unsafe_allow_html=True)
c3.markdown(stat_card("Contract Compl.", "98.5%", "#00D2AA"), unsafe_allow_html=True)
c4.markdown(stat_card("Safe Screen", "85.0%", "#FFB347"), unsafe_allow_html=True)
c5.markdown(stat_card("Exchange Eff.", "92.0%", "#00D2AA"), unsafe_allow_html=True)
c6.markdown(stat_card("Network Util.", "76.4%", "#ff416c"), unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

dark = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Outfit", color="white"), margin=dict(l=0,r=0,t=30,b=0))
stats = get_dashboard_stats()

# ── CHARTS ROW 1 ────────────────────────────────
r1c1, r1c2 = st.columns(2)
with r1c1:
    st.markdown("<div class='glass-card'><div class='section-header'>BLOOD GROUP INVENTORY</div>", unsafe_allow_html=True)
    bg_data = stats.get("units_by_group",{})
    df_bg = pd.DataFrame(list(bg_data.items()), columns=["Group","Count"])
    if not df_bg.empty:
        fig1 = px.bar(df_bg, x="Group", y="Count", color="Count", color_continuous_scale=["#302b63","#ff416c"])
        fig1.update_layout(**dark, coloraxis_showscale=False, height=250)
        st.plotly_chart(fig1, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with r1c2:
    st.markdown("<div class='glass-card'><div class='section-header'>COMPONENT DISTRIBUTION</div>", unsafe_allow_html=True)
    comp_data = stats.get("units_by_component",{})
    df_comp = pd.DataFrame(list(comp_data.items()), columns=["Comp","Count"])
    if not df_comp.empty:
        fig2 = px.pie(df_comp, values="Count", names="Comp", hole=0.6, color_discrete_sequence=["#ff416c","#FFB347","#00D2AA","#3498DB","#9B59B6"])
        fig2.update_layout(**dark, height=250)
        st.plotly_chart(fig2, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── CHARTS ROW 2 ────────────────────────────────
r2c1, r2c2 = st.columns(2)
with r2c1:
    st.markdown("<div class='glass-card'><div class='section-header'>HOSPITAL AVAILABILITY HEATMAP</div>", unsafe_allow_html=True)
    units = get_blood_units()
    if units:
        df_u = pd.DataFrame(units)
        hm = pd.crosstab(df_u["hospital_name"], df_u["blood_group"])
        fig3 = px.imshow(hm, color_continuous_scale=["#1a1a2e","#ff416c"])
        fig3.update_layout(**dark, coloraxis_showscale=False, height=250)
        st.plotly_chart(fig3, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with r2c2:
    st.markdown("<div class='glass-card'><div class='section-header'>HOSPITAL INVENTORY COMPARISON</div>", unsafe_allow_html=True)
    hospitals = get_hospitals()
    h_data = [{"Hospital": h["name"][:15], "Units": len([u for u in units if u["hospital_id"]==h["id"]])} for h in hospitals]
    df_h = pd.DataFrame(h_data)
    fig4 = px.bar(df_h, x="Hospital", y="Units", color="Units", color_continuous_scale=["#302b63","#00D2AA"])
    fig4.update_layout(**dark, coloraxis_showscale=False, height=250)
    st.plotly_chart(fig4, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── OPERATIONAL RISK MATRIX ───────────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>OPERATIONAL RISK MATRIX</div>", unsafe_allow_html=True)

risks = [
    {"Risk": "Wrong blood transfusion",  "Probability": 0.3, "Severity": 10},
    {"Risk": "Cold chain failure",        "Probability": 0.5, "Severity": 9},
    {"Risk": "Contract breach",           "Probability": 0.3, "Severity": 8},
    {"Risk": "Data integrity issue",      "Probability": 0.4, "Severity": 10},
    {"Risk": "Staff shortage",            "Probability": 0.5, "Severity": 6},
    {"Risk": "Network downtime",          "Probability": 0.2, "Severity": 9},
    {"Risk": "Inventory stockout (O+)",   "Probability": 0.6, "Severity": 8},
]
df_risk = pd.DataFrame(risks)

c1, c2 = st.columns([4, 6])
with c1:
    edited_df = st.data_editor(df_risk, hide_index=True, use_container_width=True)
with c2:
    edited_df["Score"] = edited_df["Probability"] * edited_df["Severity"]
    edited_df["Level"] = edited_df["Score"].apply(
        lambda x: "High" if x > 3.5 else ("Medium" if x > 2.0 else "Low")
    )
    fig_r = px.scatter(
        edited_df, x="Probability", y="Severity",
        size="Score", color="Level", hover_name="Risk",
        color_discrete_map={"High": "#ff416c", "Medium": "#FFB347", "Low": "#00D2AA"}
    )
    fig_r.update_layout(
        **dark,
        xaxis_title="Probability (0–1)",
        yaxis_title="Severity (1–10)"
    )
    st.plotly_chart(fig_r, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# ── NETWORK HEALTH SUMMARY ────────────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>NETWORK HEALTH SUMMARY</div>", unsafe_allow_html=True)

h_data_full = []
for h in hospitals:
    u_count  = len([u for u in units if u["hospital_id"] == h["id"]])
    critical = sum(1 for u in units if u["hospital_id"] == h["id"] and u.get("days_to_expiry", 99) <= 3)
    temp_err = sum(1 for u in units if u["hospital_id"] == h["id"] and u.get("storage_temperature", 4) > 6.0)
    if u_count == 0:
        health = "Critical"
    elif critical > 0 or temp_err > 0:
        health = "Warning"
    else:
        health = "Good"
    h_data_full.append({
        "Hospital":      h["name"],
        "Units":         u_count,
        "Expiring Soon": critical,
        "Temp Alerts":   temp_err,
        "Status":        health,
    })

df_health = pd.DataFrame(h_data_full)
for _, row in df_health.iterrows():
    color = "#00D2AA" if row["Status"] == "Good" else ("#FFB347" if row["Status"] == "Warning" else "#ff416c")
    st.markdown(f"""
    <div style='display:flex;justify-content:space-between;align-items:center;
        padding:10px 16px;border-left:3px solid {color};
        background:rgba(0,0,0,0.2);border-radius:0 8px 8px 0;margin-bottom:8px;'>
        <div style='color:white;font-weight:600;'>{row['Hospital']}</div>
        <div style='display:flex;gap:24px;'>
            <span style='color:#95A5A6;font-size:0.85rem;'>Units: <b style='color:white'>{row['Units']}</b></span>
            <span style='color:#95A5A6;font-size:0.85rem;'>Expiring: <b style='color:#FFB347'>{row['Expiring Soon']}</b></span>
            <span style='color:#95A5A6;font-size:0.85rem;'>Temp Alerts: <b style='color:#ff416c'>{row['Temp Alerts']}</b></span>
            <span class='badge {"badge-safe" if row["Status"]=="Good" else ("badge-caution" if row["Status"]=="Warning" else "badge-critical")}'>{row['Status']}</span>
        </div>
    </div>""", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
