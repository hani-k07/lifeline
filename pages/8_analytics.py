import streamlit as st
import pandas as pd
import plotly.express as px
import time

from utils.supabase_client import get_dashboard_stats, get_blood_units, get_hospitals

if not st.session_state.get("logged_in"):
    st.warning("Please login from the main page.")
    st.stop()

from utils.sidebar import render_sidebar
render_sidebar()


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
.metric-card{background:rgba(20,20,35,0.8);border:1px solid rgba(255,255,255,0.06);border-left:3px solid #ff416c;border-radius:12px;padding:18px 20px;}
.metric-value{font-size:2rem;font-weight:700;background:linear-gradient(135deg,#ff416c,#ff4b2b);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.1;}
.metric-label{font-size:0.72rem;color:#95A5A6;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:4px;}
.section-header{font-size:0.68rem;font-weight:600;color:#ff416c;text-transform:uppercase;letter-spacing:2px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid rgba(255,65,108,0.2);}
.stButton>button{background:linear-gradient(135deg,#ff416c,#ff4b2b)!important;color:white!important;border:none!important;border-radius:10px!important;font-weight:600!important;box-shadow:0 4px 15px rgba(255,65,108,0.3)!important;}
</style>""", unsafe_allow_html=True)

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
        fig1.update_layout(**dark, coloraxis_showscale=False)
        st.plotly_chart(fig1, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with r1c2:
    st.markdown("<div class='glass-card'><div class='section-header'>COMPONENT DISTRIBUTION</div>", unsafe_allow_html=True)
    comp_data = stats.get("units_by_component",{})
    df_comp = pd.DataFrame(list(comp_data.items()), columns=["Comp","Count"])
    if not df_comp.empty:
        fig2 = px.pie(df_comp, values="Count", names="Comp", hole=0.6, color_discrete_sequence=["#ff416c","#FFB347","#00D2AA","#3498DB","#9B59B6"])
        fig2.update_layout(**dark)
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
        fig3.update_layout(**dark, coloraxis_showscale=False)
        st.plotly_chart(fig3, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with r2c2:
    st.markdown("<div class='glass-card'><div class='section-header'>HOSPITAL INVENTORY COMPARISON</div>", unsafe_allow_html=True)
    hospitals = get_hospitals()
    h_data = [{"Hospital": h["name"][:15], "Units": len([u for u in units if u["hospital_id"]==h["id"]])} for h in hospitals]
    df_h = pd.DataFrame(h_data)
    fig4 = px.bar(df_h, x="Hospital", y="Units", color="Units", color_continuous_scale=["#302b63","#00D2AA"])
    fig4.update_layout(**dark, coloraxis_showscale=False)
    st.plotly_chart(fig4, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── DSA VISUALIZER ──────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>🔢 DSA: SORTING ALGORITHM VISUALIZER</div>", unsafe_allow_html=True)
c1, c2, c3 = st.columns([3, 4, 3])
algo = c1.selectbox("Select Algorithm", ["Bubble Sort"])
speed = c2.slider("Animation Speed (sec)", 0.0, 1.0, 0.1)
sort_btn = c3.button("▶ RUN VISUALIZATION", use_container_width=True)

import random
if "sort_arr" not in st.session_state:
    st.session_state.sort_arr = [random.randint(10, 100) for _ in range(15)]

plot_spot = st.empty()

def plot_arr(arr, highlight_idx=-1):
    colors = ["#ff416c" if i == highlight_idx else "#3498DB" for i in range(len(arr))]
    fig = px.bar(x=list(range(len(arr))), y=arr)
    fig.update_traces(marker_color=colors)
    fig.update_layout(**dark, xaxis_title="Index", yaxis_title="Value", xaxis_showgrid=False, yaxis_showgrid=False)
    plot_spot.plotly_chart(fig, use_container_width=True)

if sort_btn:
    arr = list(st.session_state.sort_arr)
    n = len(arr)
    comps = 0
    for i in range(n):
        for j in range(0, n-i-1):
            comps += 1
            plot_arr(arr, highlight_idx=j)
            time.sleep(speed)
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    plot_arr(arr, -1)
    st.session_state.sort_arr = arr
    st.success(f"Sorted in {comps} comparisons. O(n²) time complexity.")
else:
    plot_arr(st.session_state.sort_arr)
st.markdown("</div>", unsafe_allow_html=True)

# ── RISK MATRIX ─────────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>SE LECTURE 11: RISK ANALYSIS (P = R × S)</div>", unsafe_allow_html=True)

risks = [
    {"Risk": "Wrong blood transfusion", "Prob": 0.3, "Sev": 10},
    {"Risk": "Data breach", "Prob": 0.4, "Sev": 10},
    {"Risk": "Cold chain failure", "Prob": 0.5, "Sev": 9},
    {"Risk": "C++ integration bugs", "Prob": 0.6, "Sev": 7},
    {"Risk": "Contract breach", "Prob": 0.3, "Sev": 8},
    {"Risk": "Staff resistance", "Prob": 0.5, "Sev": 6},
    {"Risk": "Network downtime", "Prob": 0.2, "Sev": 9}
]
df_risk = pd.DataFrame(risks)

c1, c2 = st.columns([4, 6])
with c1:
    edited_df = st.data_editor(df_risk, hide_index=True)
with c2:
    edited_df["Score"] = edited_df["Prob"] * edited_df["Sev"]
    edited_df["Color"] = edited_df["Score"].apply(lambda x: "High" if x>3.5 else ("Med" if x>2.0 else "Low"))
    fig_r = px.scatter(edited_df, x="Prob", y="Sev", size="Score", color="Color", hover_name="Risk",
                       color_discrete_map={"High":"#ff416c", "Med":"#FFB347", "Low":"#00D2AA"})
    fig_r.update_layout(**dark, xaxis_title="Probability (0-1)", yaxis_title="Severity (1-10)")
    st.plotly_chart(fig_r, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# ── COCOMO CALCULATOR ───────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>SE LECTURE 9-10: COCOMO ESTIMATION MODEL</div>", unsafe_allow_html=True)

c1, c2 = st.columns([4, 6])
with c1:
    st.markdown("**Lines of Code (LOC) per Module**")
    m1 = st.slider("DB & Backend", 100, 5000, 1500)
    m2 = st.slider("DSA Engine (C++)", 100, 5000, 2000)
    m3 = st.slider("Frontend App", 100, 10000, 3500)
    kloc = (m1+m2+m3)/1000.0
    
    # Organic mode: E = 2.4 * (KLOC)^1.05, D = 2.5 * (E)^0.38
    # Semi-detached mode: E = 3.0 * (KLOC)^1.12, D = 2.5 * (E)^0.35
    effort = 3.0 * (kloc ** 1.12)
    duration = 2.5 * (effort ** 0.35)
    team = effort / duration if duration > 0 else 0

with c2:
    st.markdown(f"""<div style='display:flex;gap:15px;margin-top:20px;'>
        <div class='metric-card' style='flex:1;border-color:#3498DB;'>
            <div class='metric-label'>Total Size</div>
            <div class='metric-value'>{kloc:.1f} KLOC</div>
        </div>
        <div class='metric-card' style='flex:1;border-color:#ff416c;'>
            <div class='metric-label'>Effort</div>
            <div class='metric-value'>{effort:.1f} PM</div>
        </div>
        <div class='metric-card' style='flex:1;border-color:#00D2AA;'>
            <div class='metric-label'>Duration</div>
            <div class='metric-value'>{duration:.1f} Mo</div>
        </div>
        <div class='metric-card' style='flex:1;border-color:#FFB347;'>
            <div class='metric-label'>Team Size</div>
            <div class='metric-value'>{team:.1f} Devs</div>
        </div>
    </div>""", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
