"""Role-based access: one table drives the sidebar and the guard at the top of every page."""
from __future__ import annotations

import functools
import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import streamlit as st

from lifeline.auth import session
from lifeline.auth.roles import ADMIN_ROLES, ALL_ROLES, Role
from lifeline.bootstrap import ensure_ready
from utils import database as db

F = TypeVar("F", bound=Callable[..., Any])
logger = logging.getLogger(__name__)

# (page file, sidebar label, roles allowed). Order is the sidebar order.
PAGES: tuple[tuple[str, str, tuple[Role, ...]], ...] = (
    ("1_dashboard.py", "Dashboard", ALL_ROLES),
    ("2_inventory.py", "Inventory", ALL_ROLES),
    ("3_emergency.py", "Emergency", ALL_ROLES),
    ("4_exchange.py", "Exchange", ALL_ROLES),
    ("5_screening.py", "Screening", ALL_ROLES),
    ("6_contracts.py", "Contracts", ALL_ROLES),
    ("7_transfusion.py", "Transfusion", ALL_ROLES),
    ("8_analytics.py", "Analytics", ALL_ROLES),
    ("9_ai_center.py", "AI Center", ADMIN_ROLES),
    ("10_admin.py", "Admin Panel", (Role.SUPER_ADMIN,)),
)
PAGE_ACCESS: dict[str, tuple[Role, ...]] = {name: roles for name, _, roles in PAGES}


def can_access(role: str, page_file: str) -> bool:
    """False for unknown pages: a page missing from the table is closed, not open."""
    return role in PAGE_ACCESS.get(Path(page_file).name, ())


def nav_links(role: str) -> list[tuple[str, str]]:
    """(page path, label) pairs the given role may see."""
    return [(f"pages/{name}", label) for name, label, roles in PAGES if role in roles]


def _deny(message: str, reason: str, user: session.CurrentUser | None) -> None:
    try:
        db.add_audit_log("ACCESS_DENIED", reason, user.id if user else None)
    except sqlite3.Error:
        logger.warning("could not audit ACCESS_DENIED", exc_info=True)   # the denial itself must still happen
    st.error(message)
    st.page_link("pages/1_dashboard.py", label="← Back to dashboard")
    st.stop()


def require_page(page_file: str) -> session.CurrentUser:
    """Guard for the top of every page (call right after st.set_page_config). Returns the signed-in user.

    Sends visitors without a live session to the login page, refuses roles the access table does not list
    (and audits it), and refreshes the idle-timeout clock.
    """
    ensure_ready()
    user = session.current_user()
    if user is None:
        st.switch_page("app.py")
        st.stop()
    if session.is_expired():
        session.logout("Your session expired. Please sign in again.", expired=True)
        st.switch_page("app.py")
        st.stop()

    name = Path(page_file).name
    if user.role not in PAGE_ACCESS.get(name, ()):
        allowed = ", ".join(r.label for r in PAGE_ACCESS.get(name, ())) or "no one"
        _deny(f"Access denied. This page is restricted to: {allowed}.", f"{user.email} denied {name}", user)
    if not user.is_super and user.hospital_id is None:
        _deny("Your account is not assigned to a hospital. Ask a Super Admin to assign one.",
              f"{user.email} has no hospital assignment", user)

    session.touch()
    return user


def require_role(*roles: Role) -> Callable[[F], F]:
    """Decorator for non-page code (services): raise PermissionError unless the signed-in user has a listed role."""

    def decorate(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = session.current_user()
            if user is None or (roles and user.role not in roles):
                raise PermissionError(f"{fn.__name__} requires one of: {', '.join(r.value for r in roles) or 'login'}")
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorate
