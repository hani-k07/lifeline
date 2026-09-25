"""Transfusion reaction monitor and a graded severity score.

The monitor compares pre- and post-transfusion vitals against the proposed cut-offs in lifeline/engine/thresholds.py
(docs/CLINICAL_REFERENCE.md). It is deliberately conservative:
  * every rule is evaluated and every rule that fires is reported; the severity is the highest;
  * a missing vital is "UNKNOWN - cannot assess", never "normal" (the old monitor defaulted absent values to normal);
  * a reading outside the physiologically possible range is rejected as a data-entry error.
It never diagnoses - it recommends "stop and assess" and the clinician decides.

Reflex agent   O(r) time and space, r = number of rules (constant)
Fuzzy score    piecewise-linear "shoulder" memberships combined with a probabilistic OR. Unlike the previous triangular
               memberships, a value beyond the severe point stays fully severe instead of dropping back to zero.
               The fuzzy score is a supplementary graded view; the reflex rules decide what staff are told to do.

PEAS - reaction monitoring agent
    Performance  an adverse reaction is never reported as normal; missing data is never guessed
    Environment  one patient's vitals before and during/after a transfusion
    Actuators    severity, recommended action, the rules that fired
    Sensors      temperature, systolic BP, pulse, SpO2 (pre and post)
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from lifeline.engine.base import EngineError
from lifeline.engine.thresholds import t

VITALS = ("temp", "bp_systolic", "pulse", "o2_sat")
RANK = {"NONE": 0, "UNKNOWN": 0, "MILD": 1, "MODERATE": 2, "SEVERE": 3, "CRITICAL": 4}
ACTIONS = {
    "CRITICAL": "STOP the transfusion now. Keep the line open with saline, call the emergency team, re-check patient and unit identity.",
    "SEVERE": "STOP the transfusion. Clinician review now; return the unit and send samples to the blood bank.",
    "MODERATE": "PAUSE the transfusion. Clinician assessment before continuing; vitals every 15 minutes.",
    "MILD": "Continue with caution. Recheck vitals within 15 minutes and stop if any reading worsens.",
    "NONE": "No reaction signs in these readings. Continue routine monitoring.",
    "UNKNOWN": "A vital sign is missing, so this cannot be assessed. Measure it and run the check again.",
}
COLORS = {"CRITICAL": "red", "SEVERE": "red", "MODERATE": "amber", "MILD": "amber", "UNKNOWN": "amber", "NONE": "green"}
_RANGES = {"temp": ("range.temp_c_min", "range.temp_c_max"), "bp_systolic": ("range.sbp_min", "range.sbp_max"),
           "pulse": ("range.pulse_min", "range.pulse_max"), "o2_sat": ("range.spo2_min", "range.spo2_max")}


@dataclass(frozen=True)
class Deltas:
    temp_rise: float
    bp_drop: float
    pulse_rise: float
    o2_drop: float
    temp_post: float
    bp_post: float
    o2_post: float


@dataclass(frozen=True)
class ReactionRule:
    name: str
    severity: str
    pattern: str
    text: str
    fires: Callable[[Deltas], bool]


def _rules() -> list[ReactionRule]:
    return [
        ReactionRule("Hypoxia", "CRITICAL", "RESPIRATORY", f"SpO2 below {t('reaction.critical.spo2_post_below'):g} %",
                     lambda d: d.o2_post < t("reaction.critical.spo2_post_below")),
        ReactionRule("Severe_Hypotension", "CRITICAL", "ANAPHYLACTIC", f"Systolic BP below {t('reaction.critical.sbp_post_below'):g} mmHg",
                     lambda d: d.bp_post < t("reaction.critical.sbp_post_below")),
        ReactionRule("Shock_Pattern", "CRITICAL", "ANAPHYLACTIC",
                     f"BP drop >= {t('reaction.critical.shock_sbp_drop'):g} mmHg with pulse rise >= {t('reaction.critical.shock_pulse_rise'):g} bpm",
                     lambda d: d.bp_drop >= t("reaction.critical.shock_sbp_drop") and d.pulse_rise >= t("reaction.critical.shock_pulse_rise")),
        ReactionRule("Hypotension", "SEVERE", "HEMOLYTIC", f"Systolic BP drop >= {t('reaction.severe.sbp_drop'):g} mmHg",
                     lambda d: d.bp_drop >= t("reaction.severe.sbp_drop")),
        ReactionRule("Oxygen_Fall", "SEVERE", "RESPIRATORY",
                     f"SpO2 fall >= {t('reaction.severe.spo2_drop'):g} points or below {t('reaction.severe.spo2_post_below'):g} %",
                     lambda d: d.o2_drop >= t("reaction.severe.spo2_drop") or d.o2_post < t("reaction.severe.spo2_post_below")),
        ReactionRule("High_Fever", "SEVERE", "HEMOLYTIC", f"Temperature >= {t('reaction.severe.temp_post_at_least'):g} C",
                     lambda d: d.temp_post >= t("reaction.severe.temp_post_at_least")),
        ReactionRule("Large_Temperature_Rise", "SEVERE", "HEMOLYTIC", f"Temperature rise >= {t('reaction.severe.temp_rise'):g} C",
                     lambda d: d.temp_rise >= t("reaction.severe.temp_rise")),
        ReactionRule("Febrile_Reaction", "MODERATE", "FEBRILE",
                     f"Temperature rise >= {t('reaction.moderate.temp_rise'):g} C and now >= {t('reaction.moderate.temp_post_at_least'):g} C",
                     lambda d: d.temp_rise >= t("reaction.moderate.temp_rise") and d.temp_post >= t("reaction.moderate.temp_post_at_least")),
        ReactionRule("Marked_Tachycardia", "MODERATE", "ANAPHYLACTIC", f"Pulse rise >= {t('reaction.moderate.pulse_rise'):g} bpm",
                     lambda d: d.pulse_rise >= t("reaction.moderate.pulse_rise")),
        ReactionRule("Temperature_Rise", "MILD", "FEBRILE", f"Temperature rise >= {t('reaction.mild.temp_rise'):g} C",
                     lambda d: d.temp_rise >= t("reaction.mild.temp_rise")),
        ReactionRule("Pulse_Rise", "MILD", "ANAPHYLACTIC", f"Pulse rise >= {t('reaction.mild.pulse_rise'):g} bpm",
                     lambda d: d.pulse_rise >= t("reaction.mild.pulse_rise")),
        ReactionRule("BP_Fall", "MILD", "ANAPHYLACTIC", f"Systolic BP drop >= {t('reaction.mild.sbp_drop'):g} mmHg",
                     lambda d: d.bp_drop >= t("reaction.mild.sbp_drop")),
        ReactionRule("Oxygen_Dip", "MILD", "RESPIRATORY", f"SpO2 fall >= {t('reaction.mild.spo2_drop'):g} points",
                     lambda d: d.o2_drop >= t("reaction.mild.spo2_drop")),
    ]


def _read(vitals: Mapping[str, Any], label: str) -> tuple[dict[str, float], list[str]]:
    values: dict[str, float] = {}
    missing: list[str] = []
    for name in VITALS:
        raw = vitals.get(name)
        if raw is None:
            missing.append(f"{label} {name}")
            continue
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw != raw:
            raise EngineError(f"{label} {name} must be a number")
        low, high = (t(k) for k in _RANGES[name])
        if not low <= raw <= high:
            raise EngineError(f"{label} {name} = {raw} is outside the possible range {low:g}-{high:g}: check the entry")
        values[name] = float(raw)
    return values, missing


def monitor_reaction(pre: Mapping[str, Any], post: Mapping[str, Any]) -> dict[str, Any]:
    """Assess pre vs post vitals. See the module docstring for the guarantees."""
    before, missing_pre = _read(pre, "pre")
    after, missing_post = _read(post, "post")
    missing = missing_pre + missing_post
    if missing:
        return {"reaction_type": "UNKNOWN", "severity": "UNKNOWN", "action": ACTIONS["UNKNOWN"], "alert_color": COLORS["UNKNOWN"],
                "fired_rules": [], "missing": missing, "deltas": None, "patterns": []}
    d = Deltas(temp_rise=round(after["temp"] - before["temp"], 2), bp_drop=round(before["bp_systolic"] - after["bp_systolic"], 2),
               pulse_rise=round(after["pulse"] - before["pulse"], 2), o2_drop=round(before["o2_sat"] - after["o2_sat"], 2),
               temp_post=after["temp"], bp_post=after["bp_systolic"], o2_post=after["o2_sat"])
    fired = [r for r in _rules() if r.fires(d)]
    severity = max((r.severity for r in fired), key=lambda s: RANK[s], default="NONE")
    primary = next((r for r in fired if r.severity == severity), None)
    return {
        "reaction_type": primary.pattern if primary else "NONE", "severity": severity, "action": ACTIONS[severity],
        "alert_color": COLORS[severity], "missing": [],
        "fired_rules": [{"rule_name": r.name, "severity": r.severity, "pattern": r.pattern, "reason": r.text} for r in fired],
        "patterns": sorted({r.pattern for r in fired}),
        "deltas": {"temp_rise": d.temp_rise, "bp_drop": d.bp_drop, "pulse_rise": d.pulse_rise, "o2_change": -d.o2_drop,
                   "o2_drop": d.o2_drop},
    }


def _rising(x: float, low: float, high: float) -> float:
    """0 at or below `low`, 1 at or above `high`, straight line between (a shoulder, not a triangle)."""
    if x <= low:
        return 0.0
    if x >= high:
        return 1.0
    return (x - low) / (high - low)


def fuzzy_severity(temp_rise: float, bp_drop: float, o2_drop: float, pulse_rise: float) -> dict[str, Any]:
    """Graded 0-100 severity from fuzzy memberships (supplementary to monitor_reaction)."""
    memberships = {
        "temperature": _rising(temp_rise, t("reaction.mild.temp_rise"), t("reaction.severe.temp_rise")),
        "blood_pressure": _rising(bp_drop, t("reaction.mild.sbp_drop"), t("reaction.critical.shock_sbp_drop")),
        "oxygen": _rising(o2_drop, t("reaction.mild.spo2_drop"), t("reaction.severe.spo2_drop") + 3),
        "pulse": _rising(pulse_rise, t("reaction.mild.pulse_rise"), t("reaction.moderate.pulse_rise") + 10),
    }
    calm = 1.0
    for m in memberships.values():
        calm *= 1.0 - m                          # probabilistic OR: any single severe vital drives the score up
    score = round(100 * (1 - calm), 1)
    label = "CRITICAL" if score >= 85 else "SEVERE" if score >= 65 else "MODERATE" if score >= 40 else "MILD" if score >= 15 else "NONE"
    return {"severity_score": score, "severity_label": label, "membership_values": {k: round(v, 3) for k, v in memberships.items()}}
