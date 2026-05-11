def get_glass_css():
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Outfit', sans-serif !important; }
.stApp {
  background: linear-gradient(-45deg, #0f0c29, #302b63, #24243e, #1a1a2e);
  background-size: 400% 400%;
  animation: gradientBG 15s ease infinite;
}
@keyframes gradientBG {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
.block-container { padding-top: 1.5rem !important; }
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stHeaderActionElements"] { display: none !important; }
[data-testid="stSidebarNav"] { display: none !important; }

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0D0D1A 0%, #1C1C2E 100%) !important;
  border-right: 1px solid rgba(255,65,108,0.2);
}
[data-testid="stSidebar"] * { color: #ECF0F1 !important; }

.glass-card {
  background: rgba(20,20,35,0.7);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 16px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  transition: all 0.3s ease;
}
.glass-card:hover {
  border-color: rgba(255,65,108,0.3);
  transform: translateY(-3px);
  box-shadow: 0 12px 40px rgba(255,65,108,0.1);
}
.metric-card {
  background: rgba(20,20,35,0.8);
  border: 1px solid rgba(255,255,255,0.06);
  border-left: 3px solid #ff416c;
  border-radius: 12px;
  padding: 18px 20px;
  transition: all 0.3s ease;
}
.metric-card:hover { border-left-color:#ff4b2b; box-shadow:0 0 20px rgba(255,65,108,0.15); }
.metric-value {
  font-size:2rem; font-weight:700;
  background: linear-gradient(135deg,#ff416c,#ff4b2b);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  line-height:1.1;
}
.metric-label { font-size:0.72rem; color:#95A5A6; text-transform:uppercase; letter-spacing:1.5px; margin-bottom:4px; }
.metric-delta { font-size:0.78rem; color:#00D2AA; margin-top:4px; }

.section-header {
  font-size:0.68rem; font-weight:600; color:#ff416c;
  text-transform:uppercase; letter-spacing:2px;
  margin-bottom:14px; padding-bottom:8px;
  border-bottom:1px solid rgba(255,65,108,0.2);
}
.badge { display:inline-block; padding:3px 10px; border-radius:20px; font-size:0.7rem; font-weight:600; }
.badge-safe     { background:rgba(0,210,170,0.15);  color:#00D2AA; border:1px solid rgba(0,210,170,0.3); }
.badge-caution  { background:rgba(255,179,71,0.15); color:#FFB347; border:1px solid rgba(255,179,71,0.3); }
.badge-critical { background:rgba(255,65,108,0.15); color:#ff416c; border:1px solid rgba(255,65,108,0.3); }
.badge-blocked  { background:rgba(231,76,60,0.15);  color:#E74C3C; border:1px solid rgba(231,76,60,0.3); }
.badge-info     { background:rgba(52,152,219,0.15); color:#3498DB; border:1px solid rgba(52,152,219,0.3); }

.countdown { font-family:'Courier New',monospace; font-size:1.3rem; font-weight:700; letter-spacing:3px; }
.countdown-red   { color:#ff416c; text-shadow:0 0 10px rgba(255,65,108,0.5); }
.countdown-amber { color:#FFB347; text-shadow:0 0 10px rgba(255,179,71,0.5); }
.countdown-green { color:#00D2AA; text-shadow:0 0 10px rgba(0,210,170,0.5); }

.pulse     { animation:pulse-anim 2s infinite; }
.pulse-red { animation:pulse-red 1.5s infinite; }
@keyframes pulse-anim { 0%,100%{box-shadow:0 0 0 0 rgba(0,210,170,0.4);} 50%{box-shadow:0 0 0 8px rgba(0,210,170,0);} }
@keyframes pulse-red  { 0%,100%{box-shadow:0 0 0 0 rgba(255,65,108,0.4);} 50%{box-shadow:0 0 0 8px rgba(255,65,108,0);} }

.live-dot     { display:inline-block; width:8px; height:8px; border-radius:50%; background:#00D2AA; animation:pulse-anim 2s infinite; margin-right:6px; }
.live-dot-red { display:inline-block; width:8px; height:8px; border-radius:50%; background:#ff416c; animation:pulse-red 1s infinite; margin-right:6px; }

.alert-critical { background:linear-gradient(90deg,rgba(255,65,108,0.15),transparent); border-left:3px solid #ff416c; border-radius:0 8px 8px 0; padding:10px 16px; margin-bottom:8px; color:#ECF0F1; font-size:0.9rem; }
.alert-warning  { background:linear-gradient(90deg,rgba(255,179,71,0.15),transparent); border-left:3px solid #FFB347; border-radius:0 8px 8px 0; padding:10px 16px; margin-bottom:8px; color:#ECF0F1; font-size:0.9rem; }

.data-table { width:100%; border-collapse:collapse; }
.data-table th { background:rgba(255,65,108,0.1); color:#ff416c; font-size:0.68rem; text-transform:uppercase; letter-spacing:1px; padding:10px 14px; text-align:left; border-bottom:1px solid rgba(255,65,108,0.2); }
.data-table td { padding:10px 14px; color:#ECF0F1; font-size:0.85rem; border-bottom:1px solid rgba(255,255,255,0.03); }
.data-table tr:hover td { background:rgba(255,65,108,0.04); }

.vital-box   { background:rgba(0,0,0,0.3); border:1px solid rgba(255,255,255,0.06); border-radius:10px; padding:14px; text-align:center; }
.vital-value { font-size:1.8rem; font-weight:700; color:#ECF0F1; }
.vital-label { font-size:0.65rem; color:#95A5A6; text-transform:uppercase; letter-spacing:1px; }

.stTextInput>div>div>input,
.stSelectbox>div>div>div,
.stNumberInput>div>div>input,
.stTextArea>div>div>textarea {
  background:rgba(0,0,0,0.3) !important;
  border:1px solid rgba(255,255,255,0.1) !important;
  color:white !important;
  border-radius:10px !important;
}
.stTextInput>div>div>input:focus { border-color:#ff416c !important; box-shadow:0 0 12px rgba(255,65,108,0.25) !important; }

.stButton>button {
  background:linear-gradient(135deg,#ff416c,#ff4b2b) !important;
  color:white !important; border:none !important;
  border-radius:10px !important; font-weight:600 !important;
  letter-spacing:0.5px !important; transition:all 0.3s ease !important;
  box-shadow:0 4px 15px rgba(255,65,108,0.3) !important;
}
.stButton>button:hover { transform:translateY(-2px) !important; box-shadow:0 8px 25px rgba(255,65,108,0.5) !important; }
.stProgress > div > div { background:linear-gradient(90deg,#ff416c,#ff4b2b) !important; }
::-webkit-scrollbar { width:4px; }
::-webkit-scrollbar-track { background:rgba(255,255,255,0.02); }
::-webkit-scrollbar-thumb { background:rgba(255,65,108,0.4); border-radius:2px; }

.profile-label { color:#95A5A6; font-size:0.8rem; text-transform:uppercase; margin-bottom:2px; }
.profile-value { color:white; font-size:1.1rem; font-weight:600; margin-bottom:15px; }

</style>
"""

ROLE_COLORS = {
    "super_admin":    "#F39C12",
    "hospital_admin": "#2980B9",
    "staff":          "#00D2AA",
}
