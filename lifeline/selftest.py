"""System self-test: every engine operation against a small fixture with a known answer, plus database health.

Run from the admin console. A failure here means a deployment or a code change broke something the pages rely on."""
from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from lifeline.db.connection import connect
from lifeline.db.migrate import LATEST_VERSION, current_version
from lifeline.engine.base import OPERATIONS
from lifeline.engine.dispatcher import run_engine

NODES = [{"id": 1, "name": "Mayo", "latitude": 31.5787, "longitude": 74.3136},
         {"id": 2, "name": "Services", "latitude": 31.5497, "longitude": 74.3436},
         {"id": 3, "name": "Jinnah", "latitude": 31.4698, "longitude": 74.2728},
         {"id": 4, "name": "Shaukat Khanum", "latitude": 31.4404, "longitude": 74.4103}]
DONOR = {"age": 30, "weight": 70, "hemoglobin": 14, "bp_systolic": 120, "pulse": 72, "temperature": 36.8}
VITALS = {"temp": 36.8, "bp_systolic": 120, "pulse": 75, "o2_sat": 98}

# name -> (operation, payload, predicate over the result). Expectations are hand-checked, not copied from the code's output.
CHECKS: dict[str, tuple[str, Mapping[str, Any], Callable[[dict[str, Any]], bool]]] = {
    "Shortest road paths start at the source": (
        "dijkstra", {"nodes": NODES, "source_id": 1},
        lambda r: r["distances"][1] == 0 and len(r["distances"]) == 4 and r["paths"][3][0] == 1),
    "Backup hospitals leave out the excluded one": (
        "bfs_backup", {"nodes": NODES, "source_id": 1, "exclude_ids": [2]},
        lambda r: r["backup_hospitals"] and all(b["name"] != "Services" for b in r["backup_hospitals"])),
    "Exact blood group ranks before a substitute": (
        "find_sources", {"nodes": NODES, "source_id": 1, "blood_group": "A+", "stock": {"3": {"A+": 2}, "4": {"O-": 4}}},
        lambda r: r["options"][0]["unit_group"] == "A+" and r["options"][0]["hospital_id"] == 3
        and r["options"][-1]["unit_group"] == "O-"),
    "Earliest expiry is dispatched first": (
        "fefo_sort", {"units": [{"id": 1, "expiry_date": "2026-10-01"}, {"id": 2, "expiry_date": "2026-09-27"}], "today": "2026-09-25"},
        lambda r: [u["id"] for u in r["dispatch_order"]] == [2, 1]),
    "Merge sort orders records by key": (
        "merge_sort", {"items": [{"d": "b"}, {"d": "a"}], "key": "d"}, lambda r: [x["d"] for x in r["sorted"]] == ["a", "b"]),
    "A shortage is covered from a nearby surplus": (
        "exchange_match", {"nodes": NODES, "shortages": [{"hospital_id": 1, "blood_group": "A+", "units": 2}],
                           "surpluses": [{"hospital_id": 3, "blood_group": "A+", "units": 5}]},
        lambda r: r["matches"][0]["from_hospital_id"] == 3 and r["matches"][0]["units"] == 2),
    "A healthy donor is cleared": ("screen_donor", {"donor": DONOR}, lambda r: r["decision"] == "SAFE"),
    "Low hemoglobin defers a donor (was SAFE before the audit)": (
        "screen_donor", {"donor": {**DONOR, "hemoglobin": 9}}, lambda r: r["decision"] == "DEFER"),
    "Donor risk score stays within 0-100": ("risk_score", {"donor": DONOR}, lambda r: 0 <= r["score"] <= 100),
    "Unchanged vitals show no reaction": (
        "transfusion_monitor", {"pre": VITALS, "post": VITALS}, lambda r: r["severity"] == "NONE"),
    "Oxygen saturation of 84% is critical (was NORMAL before the audit)": (
        "transfusion_monitor", {"pre": VITALS, "post": {**VITALS, "o2_sat": 84}}, lambda r: r["severity"] == "CRITICAL"),
    "Fuzzy severity is a 0-100 score": (
        "fuzzy_severity", {"temp_rise": 1.5, "bp_drop": 25, "o2_drop": 4, "pulse_rise": 15}, lambda r: 0 <= r["severity_score"] <= 100),
    "Shortage forecast covers each group given": (
        "predict_shortage", {"groups": [{"blood_group": "O+", "stock": 10, "history": [2, 3, 2, 4]}]},
        lambda r: [p["blood_group"] for p in r["predictions"]] == ["O+"]),
    "Every donor gets a segment": (
        "cluster_donors", {"today": "2026-09-25", "donors": [{"id": i, "name": f"d{i}", "age": 20 + i, "times_donated": i, "last_donated": None}
                                                              for i in range(6)]},
        lambda r: len(r["segments"]) == 6),
    "The most urgent request comes first": (
        "triage_order", {"requests": [{"id": 1, "urgency": "ROUTINE"}, {"id": 2, "urgency": "CRITICAL"}]},
        lambda r: r["ordered"][0]["id"] == 2),
}


@dataclass(frozen=True)
class Result:
    area: str
    name: str
    ok: bool
    ms: float
    detail: str = ""


def _timed(area: str, name: str, fn: Callable[[], str | None]) -> Result:
    start = time.perf_counter()
    try:
        problem = fn()
    except Exception as exc:                  # a crash is a failed check, not a crashed self-test
        problem = f"{type(exc).__name__}: {exc}"
    return Result(area, name, problem is None, round((time.perf_counter() - start) * 1000, 2), problem or "")


def _engine_check(operation: str, payload: Mapping[str, Any], expect: Callable[[dict[str, Any]], bool]) -> Callable[[], str | None]:
    def run() -> str | None:
        return None if expect(run_engine(operation, payload)) else "the result did not match the known answer"
    return run


def _database_checks() -> list[Result]:
    def integrity() -> str | None:
        with connect() as conn:
            answer = conn.execute("PRAGMA integrity_check").fetchone()[0]
        return None if answer == "ok" else str(answer)

    def foreign_keys() -> str | None:
        with connect() as conn:
            broken = conn.execute("PRAGMA foreign_key_check").fetchall()
        return None if not broken else f"{len(broken)} row(s) point at a missing parent"

    def version() -> str | None:
        with connect() as conn:
            found = current_version(conn)
        return None if found == LATEST_VERSION else f"schema is at version {found}, the code expects {LATEST_VERSION}"

    def ledger() -> str | None:
        with connect() as conn:
            stray = conn.execute("SELECT COUNT(*) FROM blood_units WHERE status NOT IN"
                                 " ('available','reserved','issued','transfused','expired','discarded')").fetchone()[0]
        return None if stray == 0 else f"{stray} unit(s) have an unknown status"

    return [_timed("Database", "Integrity check", integrity), _timed("Database", "Foreign keys are consistent", foreign_keys),
            _timed("Database", "Schema is up to date", version), _timed("Database", "Every unit has a valid status", ledger)]


def run_all() -> list[Result]:
    results = [_timed("Engine", label, _engine_check(op, payload, expect)) for label, (op, payload, expect) in CHECKS.items()]
    covered = {op for op, _, _ in CHECKS.values()}
    results.append(_timed("Engine", "Every registered operation has a check",
                          lambda: None if covered >= set(OPERATIONS) else f"no check for: {', '.join(sorted(set(OPERATIONS) - covered))}"))
    return results + _database_checks()
