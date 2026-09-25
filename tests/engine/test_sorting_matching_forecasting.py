import random
from datetime import date

import pytest

from lifeline.engine import clustering, forecasting, matching, sorting, triage
from lifeline.engine.compatibility import can_donate

TODAY = date(2026, 9, 25)


# ------------------------------------------------------------------ FEFO / merge sort

def units(*expiries):
    return [{"id": i + 1, "expiry_date": e} for i, e in enumerate(expiries)]


def test_fefo_orders_by_expiry_sets_aside_expired_and_flags_soon():
    result = sorting.fefo_sort(units("2026-10-20", "2026-09-27", "2026-09-24", "2026-09-25", "2026-09-27"), TODAY)
    assert [u["id"] for u in result.dispatch_order] == [4, 2, 5, 1]          # ties broken by id
    assert [u["id"] for u in result.expired] == [3]                          # yesterday: never dispatched
    assert [u["id"] for u in result.expiring_soon] == [4, 2, 5]              # within 3 days
    assert sorting.fefo_sort(units("2026-09-30"), "2026-09-25", soon_days=10).expiring_soon


def test_fefo_property_output_is_sorted_and_partitions_the_input():
    rng = random.Random(3)
    for _ in range(30):
        data = [{"id": i, "expiry_date": date.fromordinal(TODAY.toordinal() + rng.randint(-5, 40)).isoformat()} for i in range(rng.randint(0, 30))]
        r = sorting.fefo_sort(data, TODAY)
        keys = [u["expiry_date"] for u in r.dispatch_order]
        assert keys == sorted(keys)
        assert len(r.dispatch_order) + len(r.expired) == len(data)
        assert all(u["expiry_date"] < TODAY.isoformat() for u in r.expired)


def test_merge_sort_equals_sorted_and_is_stable():
    rng = random.Random(11)
    for _ in range(40):
        data = [(rng.randint(0, 5), i) for i in range(rng.randint(0, 40))]      # many equal keys, i records the original order
        assert sorting.merge_sort(data, key=lambda x: x[0]) == sorted(data, key=lambda x: x[0])
        desc = sorting.merge_sort(data, key=lambda x: x[0], reverse=True)
        assert [x[0] for x in desc] == sorted((x[0] for x in data), reverse=True)
        for k in {x[0] for x in data}:                                           # equal keys keep their original order
            assert [x[1] for x in desc if x[0] == k] == sorted(x[1] for x in data if x[0] == k)
    assert sorting.merge_sort([]) == [] and sorting.merge_sort([5]) == [5]


# ------------------------------------------------------------------ triage

def test_triage_orders_by_urgency_then_waiting_time_then_id():
    reqs = [
        {"id": 1, "urgency": "ROUTINE", "created_at": "2026-09-25T08:00"},
        {"id": 2, "urgency": "CRITICAL", "created_at": "2026-09-25T09:30"},
        {"id": 3, "urgency": "CRITICAL", "created_at": "2026-09-25T09:00"},
        {"id": 4, "urgency": "URGENT", "created_at": "2026-09-25T07:00"},
        {"id": 5, "urgency": "CRITICAL", "created_at": "2026-09-25T09:00"},
    ]
    assert [r["id"] for r in triage.triage_order(reqs)] == [3, 5, 2, 4, 1]


def test_triage_queue_api_and_bad_urgency():
    q = triage.TriageQueue()
    assert q.peek() is None and len(q) == 0
    with pytest.raises(IndexError):
        q.pop()
    q.push({"id": 1, "urgency": "URGENT"})
    q.push({"id": 2, "urgency": "CRITICAL"})
    assert q.peek()["id"] == 2 and len(q) == 2 and q.pop()["id"] == 2
    with pytest.raises(ValueError):
        q.push({"id": 3, "urgency": "whenever"})


# ------------------------------------------------------------------ exchange matching

def dist(a, b):
    return abs(a - b) * 2.0


def test_matching_prefers_exact_then_nearest_and_never_matches_incompatible_blood():
    shortages = [{"hospital_id": 1, "blood_group": "A+", "units": 5}]
    surpluses = [{"hospital_id": 2, "blood_group": "A+", "units": 3}, {"hospital_id": 6, "blood_group": "A+", "units": 9},
                 {"hospital_id": 3, "blood_group": "O-", "units": 9}, {"hospital_id": 4, "blood_group": "B+", "units": 9}]
    r = matching.exchange_match(shortages, surpluses, dist)
    assert [(m["from_hospital_id"], m["unit_group"], m["units"]) for m in r["matches"]] == [(2, "A+", 3), (6, "A+", 2)]
    assert r["unmet"] == []
    assert all(can_donate(m["unit_group"], m["needed_group"]) for m in r["matches"])


def test_matching_falls_back_to_compatible_and_reports_unmet():
    r = matching.exchange_match([{"hospital_id": 1, "blood_group": "AB+", "units": 6}],
                                [{"hospital_id": 2, "blood_group": "A-", "units": 2}, {"hospital_id": 3, "blood_group": "O-", "units": 1}], dist)
    assert [(m["unit_group"], m["units"]) for m in r["matches"]] == [("A-", 2), ("O-", 1)]     # O- only after the specific group
    assert r["unmet"] == [{"hospital_id": 1, "blood_group": "AB+", "units": 3}]


def test_matching_does_not_send_stock_to_itself_and_does_not_double_spend():
    shortages = [{"hospital_id": 1, "blood_group": "O+", "units": 2}, {"hospital_id": 5, "blood_group": "O+", "units": 2}]
    surpluses = [{"hospital_id": 1, "blood_group": "O+", "units": 5}, {"hospital_id": 3, "blood_group": "O+", "units": 3}]
    r = matching.exchange_match(shortages, surpluses, dist)
    assert all(m["from_hospital_id"] != m["to_hospital_id"] for m in r["matches"])
    assert sum(m["units"] for m in r["matches"] if m["from_hospital_id"] == 3) <= 3
    assert sum(m["units"] for m in r["matches"] if m["from_hospital_id"] == 1) <= 5


# ------------------------------------------------------------------ forecasting

def test_wma_known_values_and_edge_cases():
    assert forecasting.wma_forecast([1, 2, 3], horizon=1, window=3) == [pytest.approx((1 * 1 + 2 * 2 + 3 * 3) / 6, abs=0.01)]
    assert forecasting.wma_forecast([], 3) == [0.0, 0.0, 0.0]
    assert forecasting.wma_forecast([4, 4, 4, 4], horizon=3, window=4) == [4.0, 4.0, 4.0]      # constant stays constant
    assert forecasting.wma_forecast([5], horizon=2, window=7) == [5.0, 5.0]
    for bad in ({"horizon": 0}, {"window": 0}):
        with pytest.raises(ValueError):
            forecasting.wma_forecast([1, 2], **bad)
    with pytest.raises(ValueError):
        forecasting.wma_forecast([1, -2])


def test_linear_trend():
    assert forecasting.linear_trend([1, 2, 3, 4, 5]) == pytest.approx(1.0)
    assert forecasting.linear_trend([5, 5, 5]) == 0
    assert forecasting.linear_trend([9, 7, 5]) == pytest.approx(-2.0)
    assert forecasting.linear_trend([3]) == 0


@pytest.mark.parametrize(
    ("stock", "forecast", "days", "level", "reorder"),
    [
        (0, [2, 2, 2], 0, "CRITICAL", 9),            # empty with demand coming
        (3, [2, 2, 2, 2, 2, 2, 2], 2, "CRITICAL", 18),   # 2 + 2 >= 3 on day 2
        (7, [2, 2, 2, 2, 2, 2, 2], 4, "HIGH", 14),
        (13, [2, 2, 2, 2, 2, 2, 2], 7, "MEDIUM", 8),     # lasts the whole week but under the 1.5x buffer
        (50, [2, 2, 2, 2, 2, 2, 2], None, "LOW", 0),
        (0, [0, 0, 0], None, "LOW", 0),                  # nothing used, nothing to run out of
    ],
)
def test_shortage_risk(stock, forecast, days, level, reorder):
    risk = forecasting.shortage_risk(stock, forecast)
    assert (risk.days_until_stockout, risk.risk_level, risk.recommended_reorder) == (days, level, reorder)


def test_shortage_risk_validation_and_predict_shortage_rows():
    with pytest.raises(ValueError):
        forecasting.shortage_risk(-1, [1])
    rows = forecasting.predict_shortage([{"blood_group": "O+", "stock": 6, "history": [3, 3, 4, 4, 5, 5, 6]},
                                         {"blood_group": "AB-", "stock": 0, "history": []}])
    o, ab = rows
    assert o["trend"] == "rising" and o["risk_level"] in ("CRITICAL", "HIGH") and len(o["forecast"]) == 7
    assert ab["risk_level"] == "LOW" and ab["avg_daily_demand"] == 0.0 and ab["days_until_stockout"] is None


# ------------------------------------------------------------------ clustering

def donor(i, age, times, last):
    return {"id": i, "name": f"D{i}", "age": age, "times_donated": times, "last_donated": last}


def population():
    core = [donor(i, 30 + i % 5, 12 + i % 3, "2026-08-20") for i in range(10)]
    lapsed = [donor(100 + i, 45 + i % 5, 2, "2024-01-15") for i in range(10)]
    new = [donor(200 + i, 22 + i % 3, 1, "2026-09-01") for i in range(10)]
    return core + lapsed + new


def test_segments_are_named_from_the_centres_and_separate_obvious_groups():
    result = clustering.segment_donors(population(), TODAY)
    seg = {s["donor_id"]: s["segment"] for s in result["segments"]}
    assert {seg[i] for i in range(10)} == {"CORE"}
    assert {seg[100 + i] for i in range(10)} == {"LAPSED"}
    assert {seg[200 + i] for i in range(10)} == {"OCCASIONAL"}
    assert [s["segment"] for s in result["summary"]] == ["CORE", "OCCASIONAL", "LAPSED"]
    assert sum(s["count"] for s in result["summary"]) == 30


def test_clustering_is_deterministic_and_handles_small_inputs():
    a = clustering.segment_donors(population(), TODAY)
    assert a == clustering.segment_donors(population(), TODAY)
    assert clustering.segment_donors([], TODAY) == {"segments": [], "summary": []}
    one = clustering.segment_donors([donor(1, 30, 3, None)], TODAY)
    assert one["segments"][0]["segment"] == "OCCASIONAL"
    two = clustering.segment_donors([donor(1, 30, 9, "2026-09-01"), donor(2, 50, 0, None)], TODAY, k=5)      # k larger than n
    assert len(two["segments"]) == 2


def test_kmeans_basics():
    labels, centres = clustering.kmeans([[0.0], [0.1], [10.0], [10.2]], 2)
    assert labels[0] == labels[1] != labels[2] == labels[3] and len(centres) == 2
    assert clustering.kmeans([], 3) == ([], [])
    same = clustering.kmeans([[1.0], [1.0], [1.0]], 3)
    assert len(same[0]) == 3                                                   # identical points do not crash k-means++
