"""Once-per-process startup work shared by the login page and every page."""
from __future__ import annotations

import logging
import threading
import time

import streamlit as st

from lifeline.auth.service import upgrade_known_legacy_hashes
from lifeline.db.migrate import DatabaseNotInitialised, ensure_schema
from lifeline.demo import DEMO_PASSWORD
from lifeline.services import housekeeping

logger = logging.getLogger(__name__)
HOUSEKEEPING_INTERVAL_SECONDS = 60
_lock = threading.Lock()
_last_run = 0.0


@st.cache_resource(show_spinner=False)
def _startup() -> None:
    ensure_schema()
    # Demo accounts created before bcrypt carry a legacy SHA-256 hash of a publicly known password.
    upgrade_known_legacy_hashes([DEMO_PASSWORD])


def _housekeeping_if_due() -> None:
    """Expire units, flag overdue loans and refresh stock status, at most once a minute per server process."""
    global _last_run
    with _lock:
        if time.monotonic() - _last_run < HOUSEKEEPING_INTERVAL_SECONDS:
            return
        _last_run = time.monotonic()
    try:
        housekeeping.run()
    except Exception:       # never take a page down because a background sweep failed
        logger.exception("housekeeping failed")


def ensure_ready() -> None:
    """Migrate the DB on first use; show a plain message instead of a traceback if it is missing."""
    try:
        _startup()
    except DatabaseNotInitialised as exc:
        st.error(str(exc))
        st.stop()
    _housekeeping_if_due()
