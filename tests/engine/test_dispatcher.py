import re
from pathlib import Path

import pytest

from lifeline.engine.base import OPERATIONS, EngineError
from lifeline.engine.dispatcher import describe, run_engine
from lifeline.engine.thresholds import THRESHOLDS
from scripts.seed_demo import HOSPITALS

NODES = [{"id": h[0], "name": h[1], "latitude": h[3], "longitude": h[4]} for h in HOSPITALS]
DONOR = {"age": 30, "weight": 70, "hemoglobin": 14, "bp_systolic": 120, "pulse": 72, "temperature": 36.8}
PRE = {"temp": 36.8, "bp_systolic": 120, "pulse": 75, "o2_sat": 98}

FIXTURES = {
    "dijkstra": {"nodes": NODES, "source_id": 1},
    "bfs_backup": {"nodes": NODES, "source_id": 1, "exclude_ids": [2]},
    "find_sources": {"nodes": NODES, "source_id": 1, "blood_group": "A+", "stock": {"3": {"A+": 2}, "5": {"O-": 4}}},
    "fefo_sort": {"units": [{"id": 1, "expiry_date": "2026-10-01"}, {"id": 2, "expiry_date": "2026-09-27"}], "today": "2026-09-25"},
    "merge_sort": {"items": [{"d": "b"}, {"d": "a"}], "key": "d"},
    "exchange_match": {"nodes": NODES, "shortages": [{"hospital_id": 1, "blood_group": "A+", "units": 2}],
                       "surpluses": [{"hospital_id": 3, "blood_group": "A+", "units": 5}]},
    "screen_donor": {"donor": DONOR},
    "risk_score": {"donor": DONOR},
    "transfusion_monitor": {"pre": PRE, "post": PRE},
    "fuzzy_severity": {"temp_rise": 1.5, "bp_drop": 25, "o2_drop": 4, "pulse_rise": 15},
    "predict_shortage": {"groups": [{"blood_group": "O+", "stock": 10, "history": [2, 3, 2, 4]}]},
    "cluster_donors": {"today": "2026-09-25", "donors": [{"id": i, "name": f"d{i}", "age": 20 + i, "times_donated": i, "last_donated": None} for i in range(6)]},
    "triage_order": {"requests": [{"id": 1, "urgency": "ROUTINE"}, {"id": 2, "urgency": "CRITICAL"}]},
}


def test_every_registered_operation_has_a_working_fixture_and_metadata():
    assert set(FIXTURES) == set(OPERATIONS)                       # a new operation must come with a fixture
    for name, payload in FIXTURES.items():
        result = run_engine(name, payload)
        assert isinstance(result, dict) and result, name
    for op in describe():
        assert op.summary and op.complexity.startswith("O(") and op.used_by
        assert all((op.peas.performance, op.peas.environment, op.peas.actuators, op.peas.sensors))


def test_operation_results_are_meaningful():
    assert run_engine("dijkstra", FIXTURES["dijkstra"])["paths"][3][0] == 1
    options = run_engine("find_sources", FIXTURES["find_sources"])["options"]
    assert options[0]["unit_group"] == "A+" and options[0]["hospital_id"] == 3
    assert [u["id"] for u in run_engine("fefo_sort", FIXTURES["fefo_sort"])["dispatch_order"]] == [2, 1]
    assert run_engine("merge_sort", FIXTURES["merge_sort"])["sorted"] == [{"d": "a"}, {"d": "b"}]
    assert run_engine("exchange_match", FIXTURES["exchange_match"])["matches"][0]["from_hospital_id"] == 3
    assert run_engine("triage_order", FIXTURES["triage_order"])["ordered"][0]["id"] == 2
    assert run_engine("transfusion_monitor", FIXTURES["transfusion_monitor"])["severity"] == "NONE"
    assert run_engine("screen_donor", FIXTURES["screen_donor"])["decision"] == "SAFE"


def test_unknown_operation_and_bad_payloads_raise_engine_error():
    with pytest.raises(EngineError, match="unknown operation"):
        run_engine("naive_bayes_classify", {})                     # removed on purpose: it trained on invented data
    with pytest.raises(EngineError, match="payload"):
        run_engine("dijkstra", [1, 2])                             # type: ignore[arg-type]
    for name, payload in [
        ("dijkstra", {}), ("dijkstra", {"nodes": [], "source_id": 1}), ("dijkstra", {"nodes": NODES, "source_id": 99}),
        ("dijkstra", {"nodes": [{"id": 1}], "source_id": 1}), ("dijkstra", {"nodes": NODES + [NODES[0]], "source_id": 1}),
        ("dijkstra", {"nodes": NODES, "edges": [{"from": 1, "to": 2, "weight": -1}], "source_id": 1}),
        ("dijkstra", {"nodes": NODES, "edges": [{"from": 1}], "source_id": 1}),
        ("fefo_sort", {"units": [{"id": 1}], "today": "2026-09-25"}), ("fefo_sort", {"units": "x", "today": "2026-09-25"}),
        ("merge_sort", {"items": [{"a": 1}], "key": "zzz"}), ("merge_sort", {"items": [{"a": 1}, {"a": "x"}], "key": "a"}),
        ("screen_donor", {"donor": {"age": "x"}}), ("screen_donor", {}),
        ("transfusion_monitor", {"pre": PRE, "post": {**PRE, "temp": 99}}),
        ("fuzzy_severity", {"temp_rise": "hot"}), ("predict_shortage", {"groups": [{"blood_group": "A+", "stock": -1}]}),
        ("predict_shortage", {"groups": [{"blood_group": "A+"}]}), ("predict_shortage", {"groups": [], "horizon": 0}),
        ("cluster_donors", {"donors": [], "today": "not-a-date"}), ("triage_order", {"requests": [{"id": 1, "urgency": "eh"}]}),
        ("find_sources", {"nodes": NODES, "source_id": 1, "blood_group": "Q+", "stock": {}}),
    ]:
        with pytest.raises(EngineError):
            run_engine(name, payload)


def test_explicit_edges_are_honoured_instead_of_building_a_road_graph():
    payload = {"nodes": NODES[:3], "edges": [{"from": 1, "to": 2, "weight": 10}, {"from": 2, "to": 3, "weight": 5}], "source_id": 1}
    result = run_engine("dijkstra", payload)
    assert result["distances"] == {1: 0.0, 2: 10.0, 3: 15.0} and result["paths"][3] == [1, 2, 3]


# ------------------------------------------------------------------ the written reference matches the code

def _doc_rows() -> dict[str, float]:
    text = (Path(__file__).resolve().parents[2] / "docs" / "CLINICAL_REFERENCE.md").read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        m = re.match(r"\|\s*((?:donor|reaction|range)\.[\w.]+)\s*\|\s*([\d.]+)\s*\|", line)
        if m:
            rows[m.group(1)] = float(m.group(2))
    return rows


def test_clinical_reference_document_matches_the_thresholds_in_code():
    doc = _doc_rows()
    assert set(doc) == set(THRESHOLDS), (set(doc) ^ set(THRESHOLDS))
    assert {k: v for k, v in doc.items() if v != THRESHOLDS[k]} == {}
