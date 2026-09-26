"""Page-load budget: every page's script run must finish in under 1.5 s on the seeded demo data (measured: about 0.03-0.1 s)."""
import time

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from lifeline.config import ROOT

BUDGET_SECONDS = 1.5
PAGES = ["1_dashboard", "2_inventory", "3_emergency", "4_exchange", "5_screening",
         "6_contracts", "7_transfusion", "8_analytics", "9_ai_center", "10_admin"]


def render(page):
    at = AppTest.from_file(str(ROOT / f"pages/{page}.py"), default_timeout=60)
    for k, v in dict(logged_in=True, user_id=1, user_email="admin@lifeline.com", user_name="Admin", user_role="super_admin",
                     user_hospital_id=None, user_hospital_name="Global", last_active=time.time()).items():
        at.session_state[k] = v
    start = time.perf_counter()
    at.run()
    elapsed = time.perf_counter() - start
    assert not at.exception, page
    return elapsed


@pytest.fixture(autouse=True)
def env(monkeypatch, demo_db):
    monkeypatch.setattr(st, "page_link", lambda *a, **k: None)
    monkeypatch.setattr(st, "switch_page", lambda *a, **k: None)
    render("1_dashboard")                          # warm the imports once; a real server pays this at start-up, not per page view


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_within_the_budget(page):
    assert render(page) < BUDGET_SECONDS
