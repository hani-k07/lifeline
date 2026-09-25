# utils/styles.py
from __future__ import annotations
import streamlit as st
import html

BLOOD_COLORS = {
    "A+": "#FF6B6B", "A-": "#FF8E53", "B+": "#4ECDC4", "B-": "#44A8B3",
    "AB+": "#A855F7", "AB-": "#7C3AED", "O+": "#F59E0B", "O-": "#D97706"
}

STATUS_STYLES = {
    "CRITICAL": ("CRITICAL", "#FF3D71", "rgba(255,61,113,0.15)"),
    "URGENT":   ("URGENT",   "#FFB800", "rgba(255,184,0,0.15)"),
    "ROUTINE":  ("ROUTINE",  "#00D68F", "rgba(0,214,143,0.15)"),
    "PENDING":  ("PENDING",  "#0095FF", "rgba(0,149,255,0.15)"),
    "RESOLVED": ("RESOLVED", "#00D68F", "rgba(0,214,143,0.15)"),
    "EXPIRED":  ("EXPIRED",  "#4A5568", "rgba(74,85,104,0.15)"),
    "ACTIVE":   ("ACTIVE",   "#00D68F", "rgba(0,214,143,0.15)"),
}

def get_theme() -> str:
    return st.session_state.get("theme", "dark")

def get_full_css(theme: str = "dark") -> str:
    is_dark = theme == "dark"
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Syne:wght@700;800&display=swap');

:root {{
    --bg-base:        {'#080B14' if is_dark else '#F0F2F8'};
    --bg-surface:     {'#0F1421' if is_dark else '#FFFFFF'};
    --bg-elevated:    {'#161C2D' if is_dark else '#F8FAFF'};
    --bg-hover:       {'#1E2640' if is_dark else '#EEF2FF'};
    --border-subtle:  {'#1E2640' if is_dark else '#E2E8F0'};
    --border-default: {'#2A3352' if is_dark else '#CBD5E1'};
    --border-accent:  {'#FF2D55' if is_dark else '#C41230'};
    --text-primary:   {'#F0F4FF' if is_dark else '#0F172A'};
    --text-secondary: {'#8892AA' if is_dark else '#475569'};
    --text-muted:     {'#4A5568' if is_dark else '#94A3B8'};
    --red-bright:     {'#FF2D55' if is_dark else '#C41230'};
    --red-glow:       {'rgba(255,45,85,0.15)' if is_dark else 'rgba(196,18,48,0.08)'};
    --success:        {'#00D68F' if is_dark else '#059669'};
    --warning:        {'#FFB800' if is_dark else '#D97706'};
    --danger:         {'#FF3D71' if is_dark else '#DC2626'};
    --info:           {'#0095FF' if is_dark else '#2563EB'};
    --ai-green:       {'#00FFB2' if is_dark else '#047857'};
    --shadow-card:    {'0 4px 24px rgba(0,0,0,0.4)' if is_dark else '0 2px 12px rgba(0,0,0,0.08)'};
    --glass-bg:       {'rgba(15,20,33,0.75)' if is_dark else 'rgba(255,255,255,0.8)'};
    color-scheme:     {'dark' if is_dark else 'light'};
}}

* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body, .stApp {{
    font-family: 'Inter', sans-serif;
    background: var(--bg-base) !important;
    color: var(--text-primary);
    font-size: 15px;
    line-height: 1.6;
}}

.stApp > header {{ background: transparent !important; }}
.block-container {{ padding: 1.5rem 2rem !important; max-width: 1400px !important; }}
.stButton > button {{
    background: var(--red-bright) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    padding: 0.5rem 1.2rem !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.02em !important;
}}
.stButton > button:hover {{
    filter: brightness(1.15) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px var(--red-glow) !important;
}}
.stButton > button[kind="secondary"] {{
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-default) !important;
    color: var(--text-primary) !important;
}}
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea {{
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
}}
.stTextInput > div > div > input:focus,
.stSelectbox > div > div:focus-within,
.stTextArea > div > div > textarea:focus {{
    border-color: var(--red-bright) !important;
    box-shadow: 0 0 0 2px var(--red-glow) !important;
}}
.stTabs [data-baseweb="tab-list"] {{
    background: var(--bg-surface) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 4px !important;
    border: 1px solid var(--border-subtle) !important;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent !important;
    color: var(--text-secondary) !important;
    border-radius: 7px !important;
    font-weight: 500 !important;
    font-size: 0.82rem !important;
    padding: 6px 16px !important;
    border: none !important;
}}
.stTabs [aria-selected="true"] {{
    background: var(--red-bright) !important;
    color: white !important;
}}
[data-testid="stSidebar"] {{
    background: {'#0A0D18' if is_dark else '#FFFFFF'} !important;
    border-right: 1px solid var(--border-subtle) !important;
}}
[data-testid="stSidebar"] .stButton > button {{
    background: var(--bg-elevated) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-default) !important;
    width: 100% !important;
    text-align: left !important;
}}
.stDataFrame {{ background: var(--bg-surface) !important; border-radius: 10px !important; }}
.stMetric {{ background: var(--bg-surface); border-radius: 10px; padding: 16px; border: 1px solid var(--border-subtle); }}
.stMetric label {{ color: var(--text-secondary) !important; font-size: 0.78rem !important; text-transform: uppercase; letter-spacing: 0.05em; }}
.stMetric [data-testid="metric-container"] > div:nth-child(2) {{
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 2rem !important;
    color: var(--text-primary) !important;
}}
.stProgress > div > div {{ background: var(--border-default) !important; border-radius: 4px; }}
.stProgress > div > div > div {{ background: var(--red-bright) !important; }}
div[data-testid="stForm"] {{
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 24px;
}}

.metric-card {{
    background: var(--bg-surface);
    border: 1px solid var(--border-default);
    border-radius: 16px;
    padding: 20px 24px;
    box-shadow: var(--shadow-card);
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
}}
.metric-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--red-bright), transparent);
}}
.metric-card:hover {{
    border-color: var(--border-accent);
    transform: translateY(-2px);
    box-shadow: var(--shadow-card), 0 0 20px var(--red-glow);
}}
.metric-icon {{ font-size: 1.5rem; margin-bottom: 8px; }}
.metric-label {{
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-secondary);
    margin-bottom: 6px;
    font-weight: 500;
}}
.metric-value {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.9rem;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1;
}}
.metric-delta {{
    font-size: 0.78rem;
    margin-top: 6px;
    font-weight: 500;
}}

.glass-hero {{
    background: var(--glass-bg);
    backdrop-filter: blur(24px) saturate(180%);
    -webkit-backdrop-filter: blur(24px) saturate(180%);
    border: 1px solid {'rgba(255,255,255,0.06)' if is_dark else 'rgba(0,0,0,0.08)'};
    border-radius: 24px;
    padding: 32px;
    box-shadow: var(--shadow-card);
}}

.section-header {{ margin-bottom: 20px; }}
.section-title {{
    font-family: 'Syne', sans-serif;
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 4px;
}}
.section-subtitle {{
    font-size: 0.78rem;
    color: var(--text-secondary);
    margin-bottom: 10px;
}}
.section-divider {{
    height: 1px;
    background: linear-gradient(90deg, var(--red-bright) 0%, var(--border-subtle) 40%, transparent 100%);
}}

.blood-badge {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 10px;
    border-radius: 9999px;
    font-size: 0.72rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.04em;
}}

.status-pill {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 9999px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}

.alert-banner {{
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    margin: 8px 0;
    display: flex;
    align-items: center;
    gap: 8px;
    border-left-width: 3px;
    border-left-style: solid;
}}

.lifeline-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    background: var(--bg-surface);
    border-radius: 10px;
    overflow: hidden;
}}
.lifeline-table th {{
    background: var(--bg-elevated);
    color: var(--text-secondary);
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-subtle);
    font-weight: 600;
    text-align: left;
}}
.lifeline-table td {{
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
    font-family: 'Inter', sans-serif;
}}
.lifeline-table tr:hover td {{ background: var(--bg-hover); }}
.lifeline-table tr:last-child td {{ border-bottom: none; }}

.inv-bar-wrap {{ margin: 6px 0; }}
.inv-bar-label {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
}}
.inv-bar-value {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    font-weight: 600;
}}
.inv-bar-track {{
    width: 100%;
    height: 6px;
    background: var(--bg-elevated);
    border-radius: 9999px;
    overflow: hidden;
}}
.inv-bar-fill {{
    height: 100%;
    border-radius: 9999px;
    transition: width 0.4s ease;
}}

.ai-response-box {{
    background: {'rgba(0,255,178,0.04)' if is_dark else 'rgba(4,120,87,0.04)'};
    border: 1px solid {'rgba(0,255,178,0.2)' if is_dark else 'rgba(4,120,87,0.2)'};
    border-left: 3px solid var(--ai-green);
    border-radius: 10px;
    padding: 20px;
    font-family: 'Inter', sans-serif;
    font-size: 0.875rem;
    line-height: 1.7;
    color: var(--text-primary);
    margin-top: 16px;
    white-space: pre-wrap;
}}
.ai-response-box strong {{ color: var(--ai-green); }}

.chat-bubble-user {{
    background: var(--red-bright);
    color: white;
    border-radius: 16px 16px 4px 16px;
    padding: 10px 16px;
    max-width: 75%;
    margin-left: auto;
    font-size: 0.875rem;
}}
.chat-bubble-ai {{
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    color: var(--text-primary);
    border-radius: 16px 16px 16px 4px;
    padding: 10px 16px;
    max-width: 80%;
    font-size: 0.875rem;
    font-family: 'Inter', sans-serif;
}}

.sidebar-logo {{
    font-family: 'Syne', sans-serif;
    font-size: 1.4rem;
    font-weight: 800;
    color: var(--red-bright);
    letter-spacing: 0.1em;
    margin-bottom: 4px;
}}
.sidebar-role-badge {{
    display: inline-block;
    background: var(--red-glow);
    border: 1px solid var(--red-bright);
    color: var(--red-bright);
    border-radius: 9999px;
    padding: 2px 10px;
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 4px;
}}

.login-shell {{
    text-align: center;
    max-width: 480px;
    margin: 0 auto;
    padding-top: 40px;
}}
.login-wordmark {{
    font-family: 'Syne', sans-serif;
    font-size: 3rem;
    font-weight: 800;
    color: var(--text-primary);
    letter-spacing: 0.3em;
    text-transform: uppercase;
    line-height: 1;
}}
.login-wordmark span {{ color: var(--red-bright); }}
.login-submark {{
    font-size: 0.68rem;
    letter-spacing: 0.22em;
    color: var(--text-secondary);
    text-transform: uppercase;
    margin: 6px 0 20px;
}}
.login-divider {{
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border-default), transparent);
    margin: 16px 0;
}}

.ecg-container {{ text-align: center; margin: 12px 0; }}
.ecg-line {{ width: 100%; max-width: 480px; height: 48px; }}
@keyframes ecg-draw {{
    0%   {{ stroke-dashoffset: 1000; }}
    100% {{ stroke-dashoffset: 0; }}
}}
.ecg-animated {{
    stroke-dasharray: 1000;
    stroke-dashoffset: 1000;
    animation: ecg-draw 2.5s ease-in-out infinite alternate;
}}

::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: var(--bg-base); }}
::-webkit-scrollbar-thumb {{ background: var(--border-default); border-radius: 9999px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--red-bright); }}

/* ── Bridge: Streamlit renders links/labels/popups with its own (dark) theme colours ── */
[data-testid="stMarkdownContainer"] {{ color: var(--text-primary); }}
[data-testid="stMarkdownContainer"] :is(p, li, h1, h2, h3, h4, h5, h6, strong, em) {{ color: inherit; }}
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p,
[data-testid="stCheckbox"] label, [data-testid="stCheckbox"] label p,
[data-testid="stRadio"] label, [data-testid="stRadio"] label p,
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p {{ color: var(--text-primary) !important; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ color: var(--text-secondary) !important; }}
[data-testid="stPageLink-NavLink"], [data-testid="stPageLink-NavLink"] p {{ color: var(--text-primary) !important; }}
[data-testid="stPageLink-NavLink"]:hover, [data-testid="stPageLink-NavLink"][aria-current="page"] {{
    background: var(--bg-hover) !important;
}}
[data-testid="stExpander"] details {{ background: var(--bg-surface); border-color: var(--border-subtle) !important; }}
[data-testid="stForm"] {{ background: var(--bg-surface); }}
div[data-baseweb="popover"] > div, [data-baseweb="menu"], ul[role="listbox"] {{
    background: var(--bg-surface) !important;
    color: var(--text-primary) !important;
}}
[data-baseweb="menu"] li, ul[role="listbox"] li, ul[role="listbox"] li * {{ color: var(--text-primary) !important; }}
[data-baseweb="menu"] li:hover, ul[role="listbox"] li[aria-selected="true"], ul[role="listbox"] li:hover {{ background: var(--bg-hover) !important; }}
[data-baseweb="calendar"], [data-baseweb="calendar"] * {{ color: var(--text-primary) !important; background-color: var(--bg-surface); }}
.stSelectbox [data-baseweb="select"] *, .stNumberInput input, .stTextInput input, .stTextArea textarea, .stDateInput input {{
    color: var(--text-primary) !important;
    -webkit-text-fill-color: var(--text-primary);
}}
.stNumberInput button {{ background: var(--bg-elevated) !important; color: var(--text-primary) !important; }}
::placeholder {{ color: var(--text-secondary) !important; opacity: 1; }}
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"] {{ background: var(--bg-elevated) !important; }}
[data-baseweb="input"] button {{ background: transparent !important; color: var(--text-primary) !important; }}
[data-testid="stFormSubmitButton"] > button, [data-testid="stFormSubmitButton"] button {{
    background: var(--red-bright) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}}
[data-testid="stFormSubmitButton"] button p {{ color: #FFFFFF !important; }}
[data-baseweb="checkbox"] > span:first-of-type {{
    background-color: var(--bg-elevated) !important;
    border-color: var(--border-default) !important;
}}
[data-baseweb="checkbox"]:has(input:checked) > span:first-of-type {{
    background-color: var(--red-bright) !important;
    border-color: var(--red-bright) !important;
}}

#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
.viewerBadge_container__1QSob {{ display: none; }}
[data-testid="stToolbar"] {{ visibility: hidden; }}

/* ── Sidebar toggle button — ALWAYS visible ── */
/* The header must be visible for the hamburger to appear */
header[data-testid="stHeader"] {{
    background: {'rgba(8,11,20,0.9)' if is_dark else 'rgba(240,242,248,0.9)'} !important;
    backdrop-filter: blur(12px) !important;
    border-bottom: 1px solid var(--border-subtle) !important;
    visibility: visible !important;
    display: block !important;
}}
/* Force the collapsed-sidebar expand arrow to be visible */
[data-testid="stSidebarCollapsedControl"] {{
    visibility: visible !important;
    display: flex !important;
    opacity: 1 !important;
    pointer-events: all !important;
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: 0 8px 8px 0 !important;
}}
[data-testid="stSidebarCollapsedControl"] button {{
    color: var(--text-primary) !important;
    background: transparent !important;
}}
[data-testid="stSidebarCollapsedControl"] svg {{
    fill: var(--text-primary) !important;
}}
</style>"""

def inject_all_styles(theme: str = None) -> None:
    if theme is None:
        theme = get_theme()
    st.markdown(get_full_css(theme), unsafe_allow_html=True)

def render_theme_toggle() -> None:
    theme = get_theme()
    icon = "Light" if theme == "dark" else "Dark"
    col = st.columns([8, 1])[1]
    with col:
        if st.button(icon, key="theme_toggle", help="Toggle theme"):
            st.session_state["theme"] = "light" if theme == "dark" else "dark"
            st.rerun()

class Html(str):
    """Markup produced by this module. Anything that is not Html is escaped before rendering."""


def _h(markup: str) -> Html:
    """Strip indentation and blank lines: Markdown ends an HTML block at a blank line and turns
    4-space-indented lines that follow into a code block, which is how raw <div> text leaked onto pages."""
    lines = (raw.strip() for raw in markup.splitlines())
    return Html("\n".join(line for line in lines if line))


# Badge/pill markup we generated. pandas 3 turns str subclasses into plain str, so cells are
# recognised by exact content rather than by type. Bounded so it cannot grow without limit.
_SAFE: set[str] = set()


def _mark(markup: str) -> Html:
    out = _h(markup)
    if len(_SAFE) > 4096:
        _SAFE.clear()
    _SAFE.add(str(out))
    return out


def _e(value: object) -> str:
    """Escape for HTML unless it is markup this module generated."""
    if isinstance(value, Html) or (isinstance(value, str) and value in _SAFE):
        return str(value)
    return html.escape(str(value))


def metric_card(label: str, value: str, delta: str = "",
                delta_type: str = "neutral", icon: str = "",
                variant: str = "default") -> Html:
    delta_color = {"up": "#00D68F", "down": "#FF3D71", "neutral": "#8892AA"}[delta_type]
    delta_arrow = {"up": "↑", "down": "↓", "neutral": "→"}[delta_type]

    border_map = {
        "default":  "var(--border-default)",
        "critical": "var(--danger)",
        "success":  "var(--success)",
        "ai":       "var(--ai-green)",
    }
    glow_map = {
        "default":  "none",
        "critical": "0 0 20px rgba(255,61,113,0.2)",
        "success":  "0 0 20px rgba(0,214,143,0.2)",
        "ai":       "0 0 20px rgba(0,255,178,0.15)",
    }
    delta_html = f'<div class="metric-delta" style="color:{delta_color}">{delta_arrow} {_e(delta)}</div>' if delta else ""
    return _h(f"""
    <div class="metric-card" style="border-color:{border_map[variant]};box-shadow:{glow_map[variant]}">
        <div class="metric-icon">{_e(icon)}</div>
        <div class="metric-label">{_e(label)}</div>
        <div class="metric-value">{_e(value)}</div>
        {delta_html}
    </div>""")


def blood_badge(blood_group: str, units: int = None) -> Html:
    color = BLOOD_COLORS.get(blood_group, "#888")
    units_str = f" · {units}u" if units is not None else ""
    return _mark(f"""<span class="blood-badge" style="background:{color}20;
               border:1px solid {color};color:{color}">
               {_e(blood_group)}{units_str}</span>""")


def status_pill(status: str) -> Html:
    label, color, bg = STATUS_STYLES.get(status.upper(), (status.upper(), "#888", "rgba(136,136,136,0.1)"))
    return _mark(f"""<span class="status-pill" style="background:{bg};border:1px solid {color};color:{color}">
               {_e(label)}</span>""")


def section_header(title: str, subtitle: str = "", icon: str = "") -> None:
    sub = f'<div class="section-subtitle">{_e(subtitle)}</div>' if subtitle else ""
    st.markdown(_h(f"""
    <div class="section-header">
        <div class="section-title">{_e(icon)} {_e(title)}</div>
        {sub}
        <div class="section-divider"></div>
    </div>"""), unsafe_allow_html=True)


def alert_banner(message: str, level: str = "info") -> None:
    configs = {
        "info":    ("INFO",    "#0095FF", "rgba(0,149,255,0.1)"),
        "warning": ("WARNING", "#FFB800", "rgba(255,184,0,0.1)"),
        "danger":  ("DANGER",  "#FF3D71", "rgba(255,61,113,0.1)"),
        "success": ("OK",      "#00D68F", "rgba(0,214,143,0.1)"),
    }
    label, color, bg = configs.get(level, configs["info"])
    st.markdown(_h(f"""
    <div class="alert-banner" style="background:{bg};border-left:3px solid {color}">
        <span style="color:{color};font-weight:700;font-size:0.72rem">{label}</span> {_e(message)}
    </div>"""), unsafe_allow_html=True)


def styled_table(df) -> None:
    safe = df.astype(object).map(_e)
    styler = safe.style.set_table_attributes('class="lifeline-table"')
    if type(df.index).__name__ == "RangeIndex":
        styler = styler.hide(axis="index")
    st.markdown(_h(styler.to_html()), unsafe_allow_html=True)


def inventory_bar(blood_group: str, current: int, capacity: int = 100) -> Html:
    pct = min(100, int((current / capacity) * 100))
    color = BLOOD_COLORS.get(blood_group, "#888")
    risk_color = "#FF3D71" if pct < 20 else "#FFB800" if pct < 40 else color
    return _h(f"""
    <div class="inv-bar-wrap">
        <div class="inv-bar-label">
            {blood_badge(blood_group)}
            <span class="inv-bar-value" style="color:{risk_color}">{current}u</span>
        </div>
        <div class="inv-bar-track">
            <div class="inv-bar-fill" style="width:{pct}%;background:{risk_color}"></div>
        </div>
    </div>""")


def get_matplotlib_style(theme: str = "dark") -> dict:
    is_dark = theme == "dark"
    return {
        "figure.facecolor":  "#0F1421" if is_dark else "#FFFFFF",
        "axes.facecolor":    "#161C2D" if is_dark else "#F8FAFF",
        "axes.edgecolor":    "#2A3352" if is_dark else "#CBD5E1",
        "axes.labelcolor":   "#8892AA" if is_dark else "#475569",
        "xtick.color":       "#8892AA" if is_dark else "#475569",
        "ytick.color":       "#8892AA" if is_dark else "#475569",
        "text.color":        "#F0F4FF" if is_dark else "#0F172A",
        "grid.color":        "#1E2640" if is_dark else "#E2E8F0",
        "grid.linestyle":    "--",
        "grid.alpha":        0.5,
        "font.family":       "sans-serif",
        "font.size":         10,
    }

def chart_template() -> str:
    """Plotly template matching the active app theme."""
    return "plotly_dark" if get_theme() == "dark" else "plotly_white"


def chart_font() -> dict:
    """Explicit Plotly font: Streamlit's frontend otherwise injects its own (dark-theme) text colour."""
    return {"color": "#F0F4FF" if get_theme() == "dark" else "#0F172A", "family": "Inter, sans-serif"}


def apply_chart_style(theme: str = "dark") -> None:
    import matplotlib as mpl
    mpl.rcParams.update(get_matplotlib_style(theme))

def render_matplotlib_chart(fig, caption: str = "") -> None:
    st.markdown('<div class="chart-wrapper">', unsafe_allow_html=True)
    st.pyplot(fig, use_container_width=True)
    if caption:
        st.markdown(f'<div style="font-size:0.72rem;color:var(--text-muted);text-align:center;margin-top:4px">{caption}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def render_login_sidebar() -> None:
    st.markdown(
        "<style>[data-testid='stSidebar']{display:none!important;}</style>",
        unsafe_allow_html=True,
    )

def render_ecg() -> None:
    st.markdown(
        """<div class='ecg-container'>
        <svg class='ecg-line' viewBox='0 0 600 60' xmlns='http://www.w3.org/2000/svg'>
          <polyline class='ecg-animated'
            points='0,30 60,30 80,5 100,55 120,30 180,30 200,10 220,50 240,30 300,30
                    320,8 340,52 360,30 420,30 440,12 460,48 480,30 540,30 560,15 580,45 600,30'
            fill='none' stroke='var(--red-bright)' stroke-width='2.5' stroke-linecap='round'/>
        </svg></div>""",
        unsafe_allow_html=True,
    )

def render_ai_response(text: str) -> None:
    # Convert simple markdown **bold** to HTML strong tags
    import re
    formatted = html.escape(text)          # model output is untrusted: escape first, then add our own markup
    # Replace **text** with <strong>text</strong>
    formatted = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', formatted)
    # Replace newlines with <br>
    formatted = formatted.replace('\n', '<br>')
    st.markdown(f"<div class='ai-response-box'>{formatted}</div>", unsafe_allow_html=True)
