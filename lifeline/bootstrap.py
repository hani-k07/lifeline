"""Once-per-process startup work shared by the login page and every page."""
from __future__ import annotations

import streamlit as st

from lifeline.auth.service import upgrade_known_legacy_hashes
from lifeline.db.migrate import DatabaseNotInitialised, ensure_schema
from lifeline.demo import DEMO_PASSWORD


@st.cache_resource(show_spinner=False)
def _startup() -> None:
    ensure_schema()
    # Demo accounts created before bcrypt carry a legacy SHA-256 hash of a publicly known password.
    upgrade_known_legacy_hashes([DEMO_PASSWORD])


def ensure_ready() -> None:
    """Migrate the DB on first use; show a plain message instead of a traceback if it is missing."""
    try:
        _startup()
    except DatabaseNotInitialised as exc:
        st.error(str(exc))
        st.stop()
