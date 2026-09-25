"""LIFELINE v5.0 connection and DSA engine tests. Run: python test_connection.py"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

G, R = "\033[92m[PASS]\033[0m", "\033[91m[FAIL]\033[0m"
results: list[tuple[str, bool, str]] = []


def t(name: str, fn) -> None:
    try:
        fn()
        print(f"{G}  {name}")
        results.append((name, True, ""))
    except Exception as ex:
        print(f"{R}  {name}\n       {ex}")
        results.append((name, False, str(ex)))


def _tables() -> None:
    from supabase import create_client
    c = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    for tbl in ["hospitals", "users", "donors", "patients", "blood_units",
                "contracts", "exchange_offers", "emergency_requests", "audit_logs"]:
        res = c.table(tbl).select("id").limit(1).execute()
        print(f"         {tbl}: ok ({len(res.data or [])} rows)")


def _auth() -> None:
    from utils.supabase_client import auth_login
    r = auth_login("admin@lifeline.com", "lifeline123")
    assert r and r != "DEACTIVATED" and "role" in r, f"Got: {r!r}"
    print(f"         role={r['role']}")


def _network_edges() -> None:
    from utils.supabase_client import get_network_edges
    edges = get_network_edges()
    assert len(edges) >= 14, f"Expected bidirectional edges, got {len(edges)}"
    print(f"         {len(edges)} edges")


def _dijkstra() -> None:
    from utils.helpers import run_dsa_engine
    r = run_dsa_engine("dijkstra", {
        "source_id": "h-mayo",
        "hospitals": [{"id": "h-mayo", "name": "Mayo"}, {"id": "h-services", "name": "Services"}],
        "edges": [{"from": "h-mayo", "to": "h-services", "weight": 3.8}],
        "available_hospitals": ["h-services"],
    })
    assert "error" not in r and r["best_hospital"] == "h-services", r
    assert r["best_hospital_name"] == "Services"


def _bfs_backup() -> None:
    from utils.helpers import run_dsa_engine
    r = run_dsa_engine("bfs_backup", {
        "source_id": "h-mayo",
        "hospitals": [{"id": "h-mayo", "name": "Mayo"}, {"id": "h-jinnah", "name": "Jinnah"}],
        "edges": [{"from": "h-mayo", "to": "h-jinnah", "weight": 5.2}],
        "exclude_ids": [],
    })
    assert "backup_hospitals" in r and len(r["backup_hospitals"]) == 1


def _fefo_sort() -> None:
    from utils.helpers import run_dsa_engine
    r = run_dsa_engine("fefo_sort", {"units": [
        {"id": "u1", "expiry_date": "2026-06-20", "status": "available"},
        {"id": "u2", "expiry_date": "2026-06-10", "status": "available"},
        {"id": "u3", "expiry_date": "2026-07-01", "status": "expired"},
    ]})
    assert r["sorted_units"][0]["id"] == "u2"
    assert r["total_units"] == 3
    assert r["available_units"] == 2


def _merge_sort() -> None:
    from utils.helpers import run_dsa_engine
    r = run_dsa_engine("merge_sort", {"contracts": [
        {"id": "c1", "return_deadline": "2026-12-01", "status": "active"},
        {"id": "c2", "return_deadline": "2026-06-01", "status": "active"},
    ]})
    assert r["sorted_contracts"][0]["id"] == "c2"
    assert "overdue_count" in r


def _exchange_match() -> None:
    from utils.helpers import run_dsa_engine
    r = run_dsa_engine("exchange_match", {"offers": [
        {"id": "o1", "offering_hospital_id": "h1", "offered_blood_group": "A+",
         "requested_blood_group": "O+", "units": 2, "status": "pending"},
        {"id": "o2", "offering_hospital_id": "h2", "offered_blood_group": "O+",
         "requested_blood_group": "A+", "units": 2, "status": "pending"},
    ]})
    assert len(r["matched_pairs"]) == 1


def _risk_score() -> None:
    from utils.helpers import run_dsa_engine
    r = run_dsa_engine("risk_score", {"donor": {
        "age": 30, "hemoglobin": 14, "last_donation_days": 120,
        "on_blood_thinners": False, "diseases": [], "bp_systolic": 120,
    }})
    assert r["classification"] in ("SAFE", "DEFER", "BLOCK")
    assert "penalties" in r


def _screen_donor() -> None:
    from utils.helpers import run_dsa_engine
    r = run_dsa_engine("screen_donor", {"donor": {
        "hemoglobin": 14, "bp_systolic": 120, "bp_diastolic": 80, "pulse": 72,
        "temperature": 36.8, "weight": 65, "hiv": False, "hepb": False,
        "hepc": False, "syphilis": False, "malaria": False, "diseases": [],
    }})
    assert r["decision"] == "SAFE"
    assert "inference_chain" in r


t("Supabase connection + tables", _tables)
t("auth_login", _auth)
t("get_network_edges", _network_edges)
t("dijkstra", _dijkstra)
t("bfs_backup", _bfs_backup)
t("fefo_sort", _fefo_sort)
t("merge_sort", _merge_sort)
t("exchange_match", _exchange_match)
t("risk_score", _risk_score)
t("screen_donor", _screen_donor)

print("\n" + "=" * 50)
passed = sum(1 for _, ok, _ in results if ok)
print(f"RESULTS: {passed}/{len(results)} passed")
for name, ok, err in results:
    if not ok:
        print(f"  FAIL {name}: {err[:120]}")
print("=" * 50)
sys.exit(0 if passed == len(results) else 1)
