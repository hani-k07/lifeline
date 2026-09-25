"""Login state in st.session_state. Pages still read the flat user_* keys, so login() keeps writing them."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import streamlit as st

from lifeline.auth.roles import Role, is_valid_role
from lifeline.config import get_settings
from utils import database as db


@dataclass(frozen=True)
class CurrentUser:
    id: int
    email: str
    name: str
    role: Role
    hospital_id: int | None
    hospital_name: str

    @property
    def is_super(self) -> bool:
        return self.role is Role.SUPER_ADMIN


def login(user: dict[str, Any]) -> CurrentUser:
    hospital_id = int(user["hospital_id"]) if user.get("hospital_id") else None
    if hospital_id is None:
        hospital_name = "Global (All Hospitals)"
    else:
        hospital = db.get_hospital_by_id(hospital_id)
        hospital_name = hospital["name"] if hospital else "Unknown"
    st.session_state["logged_in"] = True
    st.session_state["user_id"] = int(user["id"])
    st.session_state["user_email"] = user["email"]
    st.session_state["user_name"] = user["name"]
    st.session_state["user_role"] = user["role"]
    st.session_state["user_hospital_id"] = hospital_id
    st.session_state["user_hospital_name"] = hospital_name
    touch()
    return CurrentUser(int(user["id"]), user["email"], user["name"], Role(user["role"]), hospital_id, hospital_name)


def current_user() -> CurrentUser | None:
    state = st.session_state
    if not state.get("logged_in") or not is_valid_role(state.get("user_role")):
        return None
    return CurrentUser(
        id=int(state.get("user_id", 0)),
        email=str(state.get("user_email", "")),
        name=str(state.get("user_name", "")),
        role=Role(state["user_role"]),
        hospital_id=state.get("user_hospital_id"),
        hospital_name=str(state.get("user_hospital_name", "")),
    )


def touch() -> None:
    st.session_state["last_active"] = time.time()


def is_expired(now: float | None = None) -> bool:
    """Idle longer than SESSION_TIMEOUT_MINUTES. A session with no activity stamp fails closed."""
    last = st.session_state.get("last_active")
    if last is None:
        return True
    return (time.time() if now is None else now) - float(last) > get_settings().session_timeout_minutes * 60


def logout(reason: str | None = None, *, expired: bool = False) -> None:
    """Audit and clear the session (keeping the theme); `reason` is shown once on the login page."""
    if st.session_state.get("logged_in"):
        db.add_audit_log(
            "SESSION_EXPIRED" if expired else "LOGOUT",
            f"{st.session_state.get('user_email', 'user')} {'timed out' if expired else 'logged out'}",
            st.session_state.get("user_id"),
        )
    theme = st.session_state.get("theme")
    st.session_state.clear()
    if theme:
        st.session_state["theme"] = theme
    if reason:
        st.session_state["_flash"] = reason
