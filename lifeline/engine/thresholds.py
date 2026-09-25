"""Every clinical cut-off the engine uses, in one place.

PROPOSED VALUES - they follow commonly published donor-selection and transfusion-reaction practice but have NOT been
signed off by a clinician. docs/CLINICAL_REFERENCE.md lists the same table; a test fails if the two disagree, so a
change here without updating (and re-approving) the document cannot slip through."""
from __future__ import annotations

THRESHOLDS: dict[str, float] = {
    # ---- donor screening (a donor outside a range is deferred)
    "donor.min_age": 18,
    "donor.max_age": 65,
    "donor.min_weight_kg": 50,
    "donor.min_hb_g_dl": 12.5,
    "donor.sbp_min": 90,
    "donor.sbp_max": 180,
    "donor.dbp_min": 50,
    "donor.dbp_max": 100,
    "donor.pulse_min": 50,
    "donor.pulse_max": 100,
    "donor.temp_max_c": 37.5,
    "donor.min_days_between_donations": 90,
    # ---- transfusion reaction monitor (changes are post minus pre; drops are pre minus post)
    "reaction.critical.spo2_post_below": 90,
    "reaction.critical.sbp_post_below": 80,
    "reaction.critical.shock_sbp_drop": 40,
    "reaction.critical.shock_pulse_rise": 20,
    "reaction.severe.sbp_drop": 30,
    "reaction.severe.spo2_drop": 5,
    "reaction.severe.spo2_post_below": 92,
    "reaction.severe.temp_post_at_least": 39.0,
    "reaction.severe.temp_rise": 2.0,
    "reaction.moderate.temp_rise": 1.0,
    "reaction.moderate.temp_post_at_least": 38.0,
    "reaction.moderate.pulse_rise": 30,
    "reaction.mild.temp_rise": 1.0,
    "reaction.mild.pulse_rise": 20,
    "reaction.mild.sbp_drop": 20,
    "reaction.mild.spo2_drop": 3,
    # ---- physiologically possible ranges: anything outside is a data-entry error, not a reading
    "range.temp_c_min": 30,
    "range.temp_c_max": 45,
    "range.sbp_min": 40,
    "range.sbp_max": 300,
    "range.pulse_min": 20,
    "range.pulse_max": 250,
    "range.spo2_min": 50,
    "range.spo2_max": 100,
}


def t(key: str) -> float:
    return THRESHOLDS[key]
