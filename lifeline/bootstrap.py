"""Once-per-process startup work shared by the login page and every page."""
from __future__ import annotations

import streamlit as st

from lifeline.db.migrate import DatabaseNotInitialised, ensure_schema


@st.cache_resource(show_spinner=False)
def _migrate_once() -> list[int]:
    return ensure_schema()


def ensure_ready() -> None:
    """Migrate the DB on first use; show a plain message instead of a traceback if it is missing."""
    try:
        _migrate_once()
    except DatabaseNotInitialised as exc:
        st.error(str(exc))
        st.stop()
