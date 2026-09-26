"""The page shell: config, auth guard, theme, sidebar and title - and a guard so users never see a traceback."""
from __future__ import annotations

import base64
import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

import streamlit as st

from lifeline.auth import rbac, session
from lifeline.ui import theme
from lifeline.ui.components import alert_banner, esc, render

logger = logging.getLogger(__name__)
ASSETS = Path(__file__).with_name("assets")
LOGO = ASSETS / "logo-mark.png"

# One consistent icon family (Material Symbols); no emoji.
NAV_ICONS = {
    "1_dashboard.py": ":material/space_dashboard:", "2_inventory.py": ":material/inventory_2:",
    "3_emergency.py": ":material/emergency:", "4_exchange.py": ":material/swap_horiz:",
    "5_screening.py": ":material/how_to_reg:", "6_contracts.py": ":material/handshake:",
    "7_transfusion.py": ":material/bloodtype:", "8_analytics.py": ":material/monitoring:",
    "9_ai_center.py": ":material/psychology:", "10_admin.py": ":material/admin_panel_settings:",
}


@lru_cache(maxsize=1)
def _logo_data_uri() -> str:
    return "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode("ascii")


def _sidebar(user: session.CurrentUser) -> None:
    with st.sidebar:
        render(f'<div class="ll-brand"><img src="{_logo_data_uri()}" width="40" height="40" alt="LIFELINE blood drop logo">'
               f'<span class="ll-brand-name">LIFE<b>LINE</b></span></div>')
        render(f'<div class="ll-userbox"><div class="ll-user-name">{esc(user.name)}</div>'
               f'<div class="ll-user-meta">{esc(user.hospital_name)}</div><span class="ll-role">{esc(user.role.label)}</span></div>')
        for path, label in rbac.nav_links(user.role):
            st.page_link(path, label=label, icon=NAV_ICONS.get(Path(path).name))
        with st.container(key="sidebar_bottom"):
            dark = st.session_state.get("theme") != "light"
            if st.button("Light theme" if dark else "Dark theme", key="sb_theme", icon=":material/contrast:", use_container_width=True):
                st.session_state["theme"] = "light" if dark else "dark"
                st.rerun()
            if st.button("Log out", key="sb_logout", icon=":material/logout:", use_container_width=True):
                session.logout()
                st.switch_page("app.py")
            render('<div class="ll-sidebar-foot">LIFELINE · Lahore blood network</div>')


def page(file: str, title: str, subtitle: str = "") -> session.CurrentUser:
    """Call first in every page: config, sign-in + role check, theme, sidebar and the page title."""
    st.set_page_config(page_title=f"{title} — LIFELINE", page_icon=str(LOGO), layout="wide", initial_sidebar_state="expanded")
    user = rbac.require_page(file)
    theme.inject()
    _sidebar(user)
    render(f'<h1 class="ll-title">{esc(title)}</h1>' + (f'<p class="ll-subtitle">{esc(subtitle)}</p>' if subtitle else ""))
    return user


def public_page(title: str) -> None:
    """Shell for pages that need no sign-in (the login page): config + theme, sidebar hidden."""
    st.set_page_config(page_title=f"{title} — LIFELINE", page_icon=str(LOGO), layout="wide", initial_sidebar_state="collapsed")
    theme.inject()
    render("<style>section[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'], [data-testid='stExpandSidebarButton'] {display:none !important}</style>")


def brand_mark(width: int = 44) -> str:
    return f'<img src="{_logo_data_uri()}" width="{width}" height="{width}" alt="LIFELINE blood drop logo">'


@contextmanager
def guard() -> Iterator[None]:
    """Wrap a page body: an unexpected error becomes a friendly message with a reference id (the traceback goes to the log,
    not the screen). Streamlit's own control flow (st.stop, st.rerun, st.switch_page) passes straight through."""
    try:
        yield
    except Exception:
        reference = uuid.uuid4().hex[:8]
        logger.exception("unhandled error on a page [ref %s]", reference)
        alert_banner(f"Something went wrong and nothing was saved. Please try again; if it keeps happening tell your administrator "
                     f"the reference {reference}.", "danger", title="Error")
