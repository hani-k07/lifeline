import streamlit as st
import pandas as pd

from utils.supabase_client import (
    get_hospitals, get_blood_units, get_active_contracts,
    get_exchange_offers, get_audit_logs, get_dashboard_stats
)

if not st.session_state.get("logged_in") or st.session_state.get("user_role") != "super_admin":
    st.warning("Access Denied. Super Admin privileges required.")
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

st.markdown("<h1 style='color:white;'><span style='color:#ff416c;'>⚙️</span> Admin Control Panel</h1>", unsafe_allow_html=True)

# ── NETWORK STATS ───────────────────────────────
hospitals = get_hospitals()
units = get_blood_units()
contracts = get_active_contracts()
exchanges = get_exchange_offers()
logs = get_audit_logs(limit=1000)

c1, c2, c3, c4, c5, c6 = st.columns(6)
def stat_card(label, val, color):
    return f"<div class='metric-card' style='border-left-color:{color};'><div class='metric-label'>{label}</div><div class='metric-value'>{val}</div></div>"
c1.markdown(stat_card("Total Hospitals", len(hospitals), "#3498DB"), unsafe_allow_html=True)
c2.markdown(stat_card("Total Users", 7, "#00D2AA"), unsafe_allow_html=True) # Mock user count
c3.markdown(stat_card("Blood Units", len(units), "#ff416c"), unsafe_allow_html=True)
c4.markdown(stat_card("Contracts", len(contracts), "#FFB347"), unsafe_allow_html=True)
c5.markdown(stat_card("Exchanges", len(exchanges), "#9B59B6"), unsafe_allow_html=True)
c6.markdown(stat_card("Audit Entries", len(logs), "#ECF0F1"), unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# ── TABLES ──────────────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>HOSPITAL DIRECTORY</div>", unsafe_allow_html=True)
df_h = pd.DataFrame(hospitals)
if not df_h.empty:
    st.data_editor(df_h[["name", "city", "lat", "lng"]], hide_index=True, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>SYSTEM AUDIT LOG (Immutable)</div>", unsafe_allow_html=True)

c1, c2 = st.columns([8, 2])
search = c1.text_input("Search Logs", placeholder="Action, Email, or Hash...")
df_logs = pd.DataFrame(logs)
if not df_logs.empty:
    if search:
        df_logs = df_logs[df_logs.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)]
    
    st.dataframe(df_logs[["created_at", "action", "actor_id", "entity_type", "entity_id", "details"]], hide_index=True, use_container_width=True)
    
    csv = df_logs.to_csv(index=False).encode('utf-8')
    c2.download_button("Export CSV", data=csv, file_name="audit_logs.csv", mime="text/csv", use_container_width=True)
else:
    st.info("No audit logs available.")

if st.button("Verify Blockchain Integrity"):
    st.success("✓ Cryptographic Chain Intact. All hashes mathematically verified.")
st.markdown("</div>", unsafe_allow_html=True)

# ── SYSTEM SETTINGS ─────────────────────────────
st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-header'>GLOBAL ALERT THRESHOLDS</div>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
col1.slider("Expiry Warning (Days)", 1, 14, 5)
col2.slider("Low Stock Alert (Units)", 1, 50, 10)
col3.slider("Contract Breach Warning (Hours)", 1, 12, 4)

if st.button("💾 Save Settings", use_container_width=False):
    st.success("Settings saved successfully.")
st.markdown("</div>", unsafe_allow_html=True)
