"""ABO/Rh red-cell compatibility. A wrong answer here is a patient-safety defect, so this is the single
source of truth and is tested against an independent rule for all 64 donor/recipient pairs."""
from __future__ import annotations

from lifeline.constants import BLOOD_GROUPS

# recipient -> donor groups whose red cells they can safely receive
BLOOD_COMPATIBILITY: dict[str, tuple[str, ...]] = {
    "A+": ("A+", "A-", "O+", "O-"),
    "A-": ("A-", "O-"),
    "B+": ("B+", "B-", "O+", "O-"),
    "B-": ("B-", "O-"),
    "AB+": ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"),
    "AB-": ("A-", "B-", "AB-", "O-"),
    "O+": ("O+", "O-"),
    "O-": ("O-",),
}


def _check(group: str) -> str:
    if group not in BLOOD_GROUPS:
        raise ValueError(f"unknown blood group: {group!r}")
    return group


def can_donate(donor_group: str, recipient_group: str) -> bool:
    """True if red cells of `donor_group` may be given to a `recipient_group` patient."""
    return _check(donor_group) in BLOOD_COMPATIBILITY[_check(recipient_group)]


def compatible_donor_groups(recipient_group: str) -> tuple[str, ...]:
    return BLOOD_COMPATIBILITY[_check(recipient_group)]


def compatible_recipient_groups(donor_group: str) -> tuple[str, ...]:
    return tuple(r for r in BLOOD_GROUPS if can_donate(donor_group, r))


def rank_donor_groups(recipient_group: str) -> list[str]:
    """Exact match first, then the remaining compatible groups, most specific (fewest recipients) first so
    universal donors such as O- are kept for patients who need them."""
    donors = list(compatible_donor_groups(recipient_group))
    donors.sort(key=lambda g: (g != recipient_group, len(compatible_recipient_groups(g)), g))
    return donors
