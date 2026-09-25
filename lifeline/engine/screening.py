"""Donor screening: a forward-chaining rule engine and a risk score built from the same rules.

Every rule is evaluated and EVERY rule that fires is reported. The decision is the most severe outcome
(BLOCK > DEFER > SAFE). A donor is only SAFE when nothing fired AND every required measurement was supplied: a missing
value is never assumed to be normal (the previous engine defaulted absent vitals to healthy numbers, and a final
"All_Clear" rule overwrote every DEFER with SAFE). Cut-offs live in lifeline/engine/thresholds.py and are documented in
docs/CLINICAL_REFERENCE.md - they are proposals awaiting clinical sign-off.

Algorithm    forward chaining over a fixed rule base (no learning, fully explainable)
Complexity   O(r) time and space, r = number of rules (constant)

PEAS - donor screening agent
    Performance  no unsafe donor is cleared; every reason for a deferral is visible to staff
    Environment  one donor's serology, vitals and history at intake
    Actuators    SAFE / DEFER / BLOCK with the rules that fired and what was not assessed
    Sensors      serology flags, age, weight, haemoglobin, blood pressure, pulse, temperature, last donation
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from lifeline.engine.base import EngineError
from lifeline.engine.thresholds import t

REQUIRED = ("age", "weight", "hemoglobin", "bp_systolic", "pulse", "temperature")
SEVERITY = {"SAFE": 0, "DEFER": 1, "BLOCK": 2}


@dataclass(frozen=True)
class Rule:
    id: str
    decision: str
    reason: str
    penalty: int                                 # points off the risk score when it fires
    check: Callable[[Mapping[str, Any]], bool]   # True = fires (only called when its inputs are present)
    needs: tuple[str, ...] = ()                  # measurements the rule cannot run without


def _has(donor: Mapping[str, Any], *words: str) -> bool:
    diseases = " ".join(str(d).lower() for d in donor.get("diseases") or [])
    return any(w in diseases for w in words)


def _rules() -> list[Rule]:
    return [
        Rule("HIV_Positive", "BLOCK", "HIV positive - permanent deferral", 100,
             lambda d: bool(d.get("hiv")) or _has(d, "hiv")),
        Rule("HepB_Positive", "BLOCK", "Hepatitis B positive - permanent deferral", 100,
             lambda d: bool(d.get("hepb")) or _has(d, "hepb", "hepatitis b")),
        Rule("HepC_Positive", "BLOCK", "Hepatitis C positive - permanent deferral", 100,
             lambda d: bool(d.get("hepc")) or _has(d, "hepc", "hepatitis c")),
        Rule("Syphilis_Positive", "DEFER", "Syphilis reactive - defer until documented treatment", 40,
             lambda d: bool(d.get("syphilis"))),
        Rule("Malaria_Positive", "DEFER", "Malaria positive - defer 3 years after treatment", 40,
             lambda d: bool(d.get("malaria"))),
        Rule("On_Blood_Thinners", "DEFER", "On anticoagulant therapy", 30,
             lambda d: bool(d.get("on_blood_thinners"))),
        Rule("Age_Out_Of_Range", "DEFER", f"Age outside {t('donor.min_age'):g}-{t('donor.max_age'):g} years", 20,
             lambda d: not t("donor.min_age") <= d["age"] <= t("donor.max_age"), ("age",)),
        Rule("Low_Weight", "DEFER", f"Weight below {t('donor.min_weight_kg'):g} kg", 10,
             lambda d: d["weight"] < t("donor.min_weight_kg"), ("weight",)),
        Rule("Low_Hemoglobin", "DEFER", f"Hemoglobin below {t('donor.min_hb_g_dl'):g} g/dL", 15,
             lambda d: d["hemoglobin"] < t("donor.min_hb_g_dl"), ("hemoglobin",)),
        Rule("Systolic_BP_Out_Of_Range", "DEFER", f"Systolic BP outside {t('donor.sbp_min'):g}-{t('donor.sbp_max'):g} mmHg", 10,
             lambda d: not t("donor.sbp_min") <= d["bp_systolic"] <= t("donor.sbp_max"), ("bp_systolic",)),
        Rule("Diastolic_BP_Out_Of_Range", "DEFER", f"Diastolic BP outside {t('donor.dbp_min'):g}-{t('donor.dbp_max'):g} mmHg", 10,
             lambda d: d.get("bp_diastolic") is not None and not t("donor.dbp_min") <= d["bp_diastolic"] <= t("donor.dbp_max")),
        Rule("Pulse_Out_Of_Range", "DEFER", f"Pulse outside {t('donor.pulse_min'):g}-{t('donor.pulse_max'):g} bpm", 10,
             lambda d: not t("donor.pulse_min") <= d["pulse"] <= t("donor.pulse_max"), ("pulse",)),
        Rule("Fever", "DEFER", f"Temperature above {t('donor.temp_max_c'):g} C - possible infection", 15,
             lambda d: d["temperature"] > t("donor.temp_max_c"), ("temperature",)),
        Rule("Donated_Too_Recently", "DEFER",
             f"Last donation less than {t('donor.min_days_between_donations'):g} days ago", 15,
             lambda d: d.get("last_donation_days") is not None and d["last_donation_days"] < t("donor.min_days_between_donations")),
    ]


def _present(donor: Mapping[str, Any], name: str) -> bool:
    return donor.get(name) is not None


_LIMITS = {"age": (0, 120), "weight": (20, 300), "hemoglobin": (3, 25), "bp_systolic": (40, 300),
           "bp_diastolic": (20, 200), "pulse": (20, 250), "temperature": (30, 45), "last_donation_days": (0, 40000)}


def validate_donor(donor: Mapping[str, Any]) -> None:
    """Numbers must be numbers and physically possible; None means "not measured" and is allowed."""
    for name, (low, high) in _LIMITS.items():
        value = donor.get(name)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
            raise EngineError(f"{name} must be a number")
        if not low <= value <= high:
            raise EngineError(f"{name} = {value} is outside the possible range {low}-{high}: check the entry")


def evaluate(donor: Mapping[str, Any]) -> dict[str, Any]:
    """Run every rule. Returns the decision, all fired rules, the trace and the measurements still missing."""
    validate_donor(donor)
    fired: list[dict[str, Any]] = []
    trace: list[str] = []
    for rule in _rules():
        missing = [n for n in rule.needs if not _present(donor, n)]
        if missing:
            trace.append(f"Not assessed: {rule.id} (missing {', '.join(missing)})")
            continue
        if rule.check(donor):
            fired.append({"rule_name": rule.id, "decision": rule.decision, "reason": rule.reason, "penalty": rule.penalty})
            trace.append(f"FIRED: {rule.id} -> {rule.decision}")
        else:
            trace.append(f"Passed: {rule.id}")
    not_assessed = [n for n in REQUIRED if not _present(donor, n)]
    if not_assessed:
        fired.append({"rule_name": "Incomplete_Assessment", "decision": "DEFER", "penalty": 20,
                      "reason": f"Cannot clear the donor: not measured - {', '.join(not_assessed)}"})
        trace.append("FIRED: Incomplete_Assessment -> DEFER")
    decision = max((f["decision"] for f in fired), key=lambda d: SEVERITY[d], default="SAFE")
    return {"decision": decision, "fired_rules": fired, "inference_chain": trace, "not_assessed": not_assessed}


def screen_donor(donor: Mapping[str, Any]) -> dict[str, Any]:
    """Screening decision for one donor (see module docstring)."""
    return evaluate(donor)


def risk_score(donor: Mapping[str, Any]) -> dict[str, Any]:
    """0-100 (higher = safer) built from the same rules, so the score and the decision cannot disagree.
    A BLOCK scores 0. Each fired rule costs its penalty once - HIV in both the serology flag and the disease list is
    one finding, not two."""
    result = evaluate(donor)
    decision = result["decision"]
    penalties = [{"rule": f["rule_name"], "deduction": -f["penalty"], "reason": f["reason"]} for f in result["fired_rules"]]
    score = 0 if decision == "BLOCK" else max(0, 100 - sum(f["penalty"] for f in result["fired_rules"]))
    recommendation = {
        "SAFE": "All screening rules passed and every required measurement was recorded.",
        "DEFER": "Defer the donor. Resolve the flagged items and re-screen.",
        "BLOCK": "Donor is not eligible. Permanent deferral pending medical review.",
    }[decision]
    return {"score": score, "classification": decision, "penalties": penalties, "recommendation": recommendation,
            "not_assessed": result["not_assessed"]}
