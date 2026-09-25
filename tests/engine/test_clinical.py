"""Screening and reaction-monitor behaviour, including every P0 failure found in the Phase 0 audit."""
import random

import pytest

from lifeline.engine import screening, transfusion
from lifeline.engine.base import EngineError
from lifeline.engine.thresholds import THRESHOLDS

HEALTHY = {"age": 30, "weight": 70, "hemoglobin": 14.0, "bp_systolic": 120, "pulse": 72, "temperature": 36.8}
PRE = {"temp": 36.8, "bp_systolic": 120, "pulse": 75, "o2_sat": 98}


def names(result):
    return [r["rule_name"] for r in result["fired_rules"]]


# ================================================================== donor screening

def test_healthy_donor_is_safe_with_nothing_fired():
    r = screening.screen_donor({**HEALTHY, "last_donation_days": 200})
    assert r["decision"] == "SAFE" and r["fired_rules"] == [] and r["not_assessed"] == []


@pytest.mark.parametrize(
    ("change", "rule"),
    [
        ({"hemoglobin": 9}, "Low_Hemoglobin"),                     # audit: used to come back SAFE
        ({"weight": 40}, "Low_Weight"),
        ({"bp_systolic": 200}, "Systolic_BP_Out_Of_Range"),
        ({"bp_systolic": 85}, "Systolic_BP_Out_Of_Range"),
        ({"bp_diastolic": 105}, "Diastolic_BP_Out_Of_Range"),
        ({"pulse": 130}, "Pulse_Out_Of_Range"),                    # audit: pulse was ignored
        ({"pulse": 45}, "Pulse_Out_Of_Range"),
        ({"temperature": 38.5}, "Fever"),                          # audit: fever was ignored
        ({"age": 70}, "Age_Out_Of_Range"),                         # audit: no age rule
        ({"age": 16}, "Age_Out_Of_Range"),
        ({"last_donation_days": 10}, "Donated_Too_Recently"),      # audit: no donation-gap rule
        ({"on_blood_thinners": True}, "On_Blood_Thinners"),
        ({"malaria": True}, "Malaria_Positive"),
        ({"syphilis": True}, "Syphilis_Positive"),
    ],
)
def test_every_vital_and_history_rule_defers(change, rule):
    r = screening.screen_donor({**HEALTHY, **change})
    assert r["decision"] == "DEFER" and rule in names(r), r


@pytest.mark.parametrize("change", [{"hiv": True}, {"hepb": True}, {"hepc": True}, {"diseases": ["HIV"]},
                                    {"diseases": ["Hepatitis B carrier"]}, {"diseases": ["hepc"]}])
def test_blood_borne_infections_block(change):
    assert screening.screen_donor({**HEALTHY, **change})["decision"] == "BLOCK"


def test_all_fired_rules_are_reported_not_just_the_first():
    r = screening.screen_donor({**HEALTHY, "hiv": True, "hemoglobin": 9, "weight": 40, "bp_systolic": 200, "temperature": 38.5})
    assert r["decision"] == "BLOCK"
    assert set(names(r)) == {"HIV_Positive", "Low_Hemoglobin", "Low_Weight", "Systolic_BP_Out_Of_Range", "Fever"}


@pytest.mark.parametrize(
    ("key", "ok", "bad"),
    [("age", 18, 17), ("age", 65, 66), ("weight", 50, 49.9), ("hemoglobin", 12.5, 12.4), ("bp_systolic", 90, 89),
     ("bp_systolic", 180, 181), ("pulse", 50, 49), ("pulse", 100, 101), ("temperature", 37.5, 37.6),
     ("last_donation_days", 90, 89)],
)
def test_boundaries_are_inclusive_on_the_safe_side(key, ok, bad):
    base = {**HEALTHY, "last_donation_days": 200}
    assert screening.screen_donor({**base, key: ok})["decision"] == "SAFE"
    assert screening.screen_donor({**base, key: bad})["decision"] == "DEFER"


def test_missing_measurements_are_never_assumed_normal():
    r = screening.screen_donor({"age": 30})                        # everything else not measured
    assert r["decision"] == "DEFER" and "Incomplete_Assessment" in names(r)
    assert set(r["not_assessed"]) == {"weight", "hemoglobin", "bp_systolic", "pulse", "temperature"}
    assert any(line.startswith("Not assessed") for line in r["inference_chain"])
    assert screening.screen_donor({})["decision"] == "DEFER"
    assert screening.screen_donor({"hiv": True})["decision"] == "BLOCK"          # a positive result still wins


def test_optional_measurements_do_not_block_a_safe_decision():
    assert screening.screen_donor(HEALTHY)["decision"] == "SAFE"                 # no diastolic, no donation history


def test_input_validation_rejects_garbage():
    for bad in ({"age": "thirty"}, {"weight": True}, {"hemoglobin": 99}, {"temperature": 3}, {"pulse": float("nan")},
                {"bp_systolic": 5}):
        with pytest.raises(EngineError):
            screening.screen_donor({**HEALTHY, **bad})


def test_risk_score_counts_each_finding_once_and_agrees_with_the_decision():
    both = screening.risk_score({**HEALTHY, "hiv": True, "diseases": ["HIV"]})            # flag + disease string = one finding
    assert both["classification"] == "BLOCK" and both["score"] == 0
    assert [p["rule"] for p in both["penalties"]] == ["HIV_Positive"]
    one = screening.risk_score({**HEALTHY, "hemoglobin": 12.0})
    assert one["score"] == 85 and one["classification"] == "DEFER"
    assert screening.risk_score(HEALTHY)["score"] == 100


def test_risk_score_and_screen_donor_never_disagree():
    rng = random.Random(5)
    for _ in range(300):
        donor = {"age": rng.randint(15, 75), "weight": rng.randint(40, 100), "hemoglobin": round(rng.uniform(9, 17), 1),
                 "bp_systolic": rng.randint(70, 200), "pulse": rng.randint(40, 130), "temperature": round(rng.uniform(36, 39), 1),
                 "last_donation_days": rng.choice([None, 10, 100, 400]), "hiv": rng.random() < 0.05,
                 "malaria": rng.random() < 0.05, "on_blood_thinners": rng.random() < 0.05}
        screen, risk = screening.screen_donor(donor), screening.risk_score(donor)
        assert risk["classification"] == screen["decision"]
        assert (risk["score"] == 100) == (screen["decision"] == "SAFE")
        assert 0 <= risk["score"] <= 100


# ================================================================== reaction monitor

def post(**changes):
    return {**PRE, **changes}


@pytest.mark.parametrize(
    ("post_vitals", "severity"),
    [
        (post(o2_sat=84, bp_systolic=110, temp=37.0), "CRITICAL"),      # audit: "NORMAL, proceeding normally"
        (post(bp_systolic=85), "SEVERE"),                               # audit: BP drop 35 alone was NORMAL
        (post(pulse=150), "MODERATE"),                                  # audit: pulse was never read
        (post(temp=38.0), "MODERATE"),                                  # audit: rise of exactly 1.0 (+ >= 38) was NORMAL
        (post(temp=37.7), "NONE"),                                      # rise 0.9: below every threshold
        (post(temp=37.9), "MILD"),                                      # rise 1.1 but under 38.0 C: watch only
        (post(temp=39.2), "SEVERE"),
        (post(o2_sat=91), "SEVERE"),                                    # below 92 %
        (post(o2_sat=93), "SEVERE"),                                    # 98 -> 93 is a 5-point fall
        (post(o2_sat=95), "MILD"),                                      # 98 -> 95 is a 3-point dip
        (post(temp=37.0, bp_systolic=118, pulse=78, o2_sat=98), "NONE"),
    ],
)
def test_monitor_severity(post_vitals, severity):
    result = transfusion.monitor_reaction(PRE, post_vitals)
    assert result["severity"] == severity, result["fired_rules"]


def test_shock_pattern_and_combined_findings():
    r = transfusion.monitor_reaction(PRE, post(bp_systolic=78, pulse=100))
    assert r["severity"] == "CRITICAL" and {x["rule_name"] for x in r["fired_rules"]} >= {"Severe_Hypotension", "Shock_Pattern"}
    r = transfusion.monitor_reaction(PRE, post(temp=39.0, bp_systolic=88))
    assert r["severity"] == "SEVERE" and "HEMOLYTIC" in r["patterns"] and r["alert_color"] == "red"
    assert "STOP" in r["action"]


def test_missing_vitals_are_unknown_never_normal():
    r = transfusion.monitor_reaction(PRE, {"temp": 37.0, "bp_systolic": 118})
    assert r["severity"] == "UNKNOWN" and r["reaction_type"] == "UNKNOWN" and r["deltas"] is None
    assert set(r["missing"]) == {"post pulse", "post o2_sat"}
    assert "cannot be assessed" in r["action"] and r["alert_color"] == "amber"
    assert transfusion.monitor_reaction({}, {})["severity"] == "UNKNOWN"


@pytest.mark.parametrize("bad", [{"temp": 55}, {"temp": 20}, {"bp_systolic": 500}, {"pulse": 5}, {"o2_sat": 120}, {"o2_sat": "98"},
                                 {"temp": float("nan")}, {"pulse": True}])
def test_impossible_readings_are_rejected(bad):
    with pytest.raises(EngineError):
        transfusion.monitor_reaction(PRE, post(**bad))
    with pytest.raises(EngineError):
        transfusion.monitor_reaction({**PRE, **bad}, PRE)


def test_deltas_and_result_shape():
    r = transfusion.monitor_reaction(PRE, post(temp=37.4, bp_systolic=110, pulse=85, o2_sat=97))
    assert r["deltas"] == {"temp_rise": 0.6, "bp_drop": 10, "pulse_rise": 10, "o2_change": -1, "o2_drop": 1}
    assert r["severity"] == "NONE" and r["fired_rules"] == [] and r["reaction_type"] == "NONE" and r["alert_color"] == "green"


@pytest.mark.parametrize(
    ("key", "build", "severity"),
    [
        ("reaction.critical.spo2_post_below", lambda v: post(o2_sat=v - 0.1), "CRITICAL"),
        ("reaction.critical.sbp_post_below", lambda v: post(bp_systolic=v - 0.1), "CRITICAL"),
        ("reaction.severe.sbp_drop", lambda v: post(bp_systolic=120 - v), "SEVERE"),
        ("reaction.severe.spo2_drop", lambda v: post(o2_sat=98 - v), "SEVERE"),
        ("reaction.severe.temp_rise", lambda v: post(temp=36.8 + v), "SEVERE"),
        ("reaction.moderate.pulse_rise", lambda v: post(pulse=75 + v), "MODERATE"),
        ("reaction.mild.sbp_drop", lambda v: post(bp_systolic=120 - v), "MILD"),
        ("reaction.mild.pulse_rise", lambda v: post(pulse=75 + v), "MILD"),
        ("reaction.mild.spo2_drop", lambda v: post(o2_sat=98 - v), "MILD"),
    ],
)
def test_every_threshold_is_live_at_its_documented_boundary(key, build, severity):
    """Exactly at the written value the rule fires (>=), just inside it does not - so the table IS the behaviour."""
    value = THRESHOLDS[key]
    at = transfusion.monitor_reaction(PRE, build(value))
    assert transfusion.RANK[at["severity"]] >= transfusion.RANK[severity], (key, at)
    if "below" in key:
        just_ok = build(value + 0.2)                                   # a hair above the "below" cut-off
    else:
        just_ok = build(value - 0.2)
    assert transfusion.RANK[transfusion.monitor_reaction(PRE, just_ok)["severity"]] < transfusion.RANK[severity], key


def test_febrile_rule_needs_both_the_rise_and_the_absolute_temperature():
    assert transfusion.monitor_reaction({**PRE, "temp": 36.5}, post(temp=37.5))["severity"] == "MILD"      # +1.0 but only 37.5
    assert transfusion.monitor_reaction({**PRE, "temp": 37.0}, post(temp=38.0))["severity"] == "MODERATE"  # +1.0 and 38.0


def test_severity_is_monotonic_as_bp_falls():
    ranks = [transfusion.RANK[transfusion.monitor_reaction(PRE, post(bp_systolic=bp))["severity"]] for bp in range(120, 60, -5)]
    assert ranks == sorted(ranks)


# ================================================================== fuzzy severity

def test_fuzzy_score_is_zero_when_calm_and_saturates_when_severe():
    assert transfusion.fuzzy_severity(0, 0, 0, 0)["severity_label"] == "NONE"
    worst = transfusion.fuzzy_severity(3.5, 70, 20, 60)
    assert worst["severity_score"] == 100.0 and worst["severity_label"] == "CRITICAL"       # the old triangles fell back to MILD here
    assert transfusion.fuzzy_severity(2.0, 0, 0, 0)["severity_label"] in ("SEVERE", "CRITICAL")


def test_fuzzy_score_never_decreases_when_a_vital_worsens():
    for key in ("temp_rise", "bp_drop", "o2_drop", "pulse_rise"):
        scores = []
        for x in [0, 0.5, 1, 2, 3, 5, 10, 20, 40, 80]:
            args = {"temp_rise": 0, "bp_drop": 0, "o2_drop": 0, "pulse_rise": 0, key: x}
            scores.append(transfusion.fuzzy_severity(**args)["severity_score"])
        assert scores == sorted(scores), key
