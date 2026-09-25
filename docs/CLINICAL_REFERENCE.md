# Clinical reference table (PROPOSED — needs clinical sign-off)

The decision logic in `lifeline/engine/screening.py` and `lifeline/engine/transfusion.py` reads its cut-offs from
`lifeline/engine/thresholds.py`. This document is the human-readable copy. A unit test parses the tables below and
fails if any value differs from the code, so the two cannot drift silently.

**Status:** proposed. The values follow commonly published donor-selection and acute-transfusion-reaction practice,
but they are **not** a substitute for your blood bank's protocol and have not been approved by a clinician. A medical
officer must review every row before the system is used on real patients or donors.

**How the software uses them:** LIFELINE never diagnoses. It flags. Any red flag on the reaction monitor recommends
*stop and assess*; it never says "safe to continue" when a reading is missing (it says "cannot assess"). The final
decision is always the clinician's.

## 1. Donor screening

Every rule is evaluated; **all** rules that fire are reported. The decision is the most severe one that fired
(BLOCK > DEFER > SAFE). A donor is SAFE only when every required measurement is present and no rule fired.

| key | value | unit | rule |
|---|---|---|---|
| donor.min_age | 18 | years | younger: DEFER |
| donor.max_age | 65 | years | older: DEFER |
| donor.min_weight_kg | 50 | kg | lighter: DEFER |
| donor.min_hb_g_dl | 12.5 | g/dL | lower haemoglobin: DEFER |
| donor.sbp_min | 90 | mmHg | lower systolic pressure: DEFER |
| donor.sbp_max | 180 | mmHg | higher systolic pressure: DEFER |
| donor.dbp_min | 50 | mmHg | lower diastolic pressure (only if measured): DEFER |
| donor.dbp_max | 100 | mmHg | higher diastolic pressure (only if measured): DEFER |
| donor.pulse_min | 50 | bpm | slower pulse: DEFER |
| donor.pulse_max | 100 | bpm | faster pulse: DEFER |
| donor.temp_max_c | 37.5 | °C | higher temperature: DEFER |
| donor.min_days_between_donations | 90 | days | shorter gap since last donation: DEFER |

Rules that do not have a number:

| finding | decision | note |
|---|---|---|
| HIV, hepatitis B or hepatitis C positive (serology flag or recorded disease) | BLOCK | permanent deferral |
| syphilis reactive | DEFER | until documented treatment. **Changed:** the old code labelled this BLOCK while its own message said "defer until treated". |
| malaria positive | DEFER | 3 years after treatment |
| on blood thinners (anticoagulants) | DEFER | **New rule** (previously only a score penalty) |
| a required measurement is missing (age, weight, haemoglobin, systolic BP, pulse, temperature) | DEFER | **Changed:** the old code silently assumed a normal value for anything not entered |

## 2. Transfusion reaction monitor

Inputs are a pre- and a post-transfusion set of vitals: temperature, systolic BP, pulse, SpO₂. Changes: *temperature
rise* and *pulse rise* = post − pre; *BP drop* and *SpO₂ drop* = pre − post. Every rule is evaluated; all that fire are
reported; the severity is the highest. Comparisons are inclusive (`>=`, `<=`) unless "below" is written.

| key | value | unit | fires when |
|---|---|---|---|
| reaction.critical.spo2_post_below | 90 | % | post SpO₂ **below** this → CRITICAL |
| reaction.critical.sbp_post_below | 80 | mmHg | post systolic **below** this → CRITICAL |
| reaction.critical.shock_sbp_drop | 40 | mmHg | BP drop ≥ this **and** pulse rise ≥ the next row → CRITICAL |
| reaction.critical.shock_pulse_rise | 20 | bpm | (see previous row) |
| reaction.severe.sbp_drop | 30 | mmHg | BP drop ≥ this → SEVERE |
| reaction.severe.spo2_drop | 5 | % points | SpO₂ drop ≥ this → SEVERE |
| reaction.severe.spo2_post_below | 92 | % | post SpO₂ **below** this → SEVERE |
| reaction.severe.temp_post_at_least | 39.0 | °C | post temperature ≥ this → SEVERE |
| reaction.severe.temp_rise | 2.0 | °C | temperature rise ≥ this → SEVERE |
| reaction.moderate.temp_rise | 1.0 | °C | rise ≥ this **and** post temperature ≥ the next row → MODERATE (febrile pattern) |
| reaction.moderate.temp_post_at_least | 38.0 | °C | (see previous row) |
| reaction.moderate.pulse_rise | 30 | bpm | pulse rise ≥ this → MODERATE |
| reaction.mild.temp_rise | 1.0 | °C | temperature rise ≥ this → MILD (watch) |
| reaction.mild.pulse_rise | 20 | bpm | pulse rise ≥ this → MILD |
| reaction.mild.sbp_drop | 20 | mmHg | BP drop ≥ this → MILD |
| reaction.mild.spo2_drop | 3 | % points | SpO₂ drop ≥ this → MILD |

| severity | recommended action shown to staff |
|---|---|
| CRITICAL | STOP the transfusion now, keep the line open with saline, call the emergency team, re-check patient and unit identity |
| SEVERE | STOP the transfusion, clinician review now, return the unit and send samples to the blood bank |
| MODERATE | PAUSE the transfusion, clinician assessment before continuing, vitals every 15 minutes |
| MILD | Continue with caution; recheck vitals within 15 minutes; stop if any reading worsens |
| NONE | No reaction signs in these readings; continue routine monitoring |
| UNKNOWN | A vital sign is missing: cannot assess. Measure it and run the check again |

Readings outside the physiological ranges below are rejected as data-entry errors (they are not evaluated):

| key | value | unit | meaning |
|---|---|---|---|
| range.temp_c_min | 30 | °C | lowest accepted temperature |
| range.temp_c_max | 45 | °C | highest accepted temperature |
| range.sbp_min | 40 | mmHg | lowest accepted systolic pressure |
| range.sbp_max | 300 | mmHg | highest accepted systolic pressure |
| range.pulse_min | 20 | bpm | lowest accepted pulse |
| range.pulse_max | 250 | bpm | highest accepted pulse |
| range.spo2_min | 50 | % | lowest accepted SpO₂ |
| range.spo2_max | 100 | % | highest accepted SpO₂ |

## 3. What changed compared with the previous engine

| Before | Now |
|---|---|
| SpO₂ 84 % with little else changed → "NORMAL" | CRITICAL (SpO₂ below 90) |
| Systolic drop of 35 mmHg alone → "NORMAL" | SEVERE (drop ≥ 30) |
| Pulse never read | pulse rise is a rule |
| Fever only counted as a *rise* strictly above 1.0 °C; absolute temperature ignored | rise ≥ 1.0 °C and post ≥ 38.0 °C → MODERATE; post ≥ 39.0 °C → SEVERE |
| Missing post vitals silently defaulted to normal values → "NORMAL" | UNKNOWN: "cannot assess" |
| Screening: a final `All_Clear` rule overwrote every DEFER with SAFE | all rules reported; SAFE only if none fired and nothing is missing |
| Screening age / pulse / temperature / donation-gap rules missing or unreachable | present and evaluated |
