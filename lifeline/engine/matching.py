"""Suggested hospital-to-hospital transfers: match shortages with surpluses.

Algorithm    hash index of surplus by blood group, then greedy allocation: the biggest shortage first, exact blood group
             before compatible ones (O- kept for last), nearest surplus first. Deterministic.
Complexity   O(S + D*G*C log C): S surplus records, D shortages, G <= 8 compatible groups, C candidate hospitals
Note         greedy, not globally optimal - it produces sensible suggestions a person then accepts or ignores.

PEAS - network balancing agent
    Performance  shortages are covered from nearby surplus with the least universal-donor stock spent
    Environment  per-hospital shortage and surplus by group, road distances
    Actuators    a list of suggested transfers (staff file the exchange request themselves)
    Sensors      stock levels against thresholds, pairwise distances
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from lifeline.engine.compatibility import rank_donor_groups


def exchange_match(shortages: Sequence[dict[str, Any]], surpluses: Sequence[dict[str, Any]],
                   distance_km: Callable[[int, int], float]) -> dict[str, Any]:
    """`shortages`/`surpluses`: dicts with hospital_id, blood_group, units. Returns matches and what stays unmet."""
    index: dict[str, list[list[int]]] = {}                    # group -> [[hospital_id, remaining units], ...]
    for s in surpluses:
        if s["units"] > 0:
            index.setdefault(s["blood_group"], []).append([int(s["hospital_id"]), int(s["units"])])

    matches: list[dict[str, Any]] = []
    unmet: list[dict[str, Any]] = []
    for need in sorted(shortages, key=lambda s: (-int(s["units"]), int(s["hospital_id"]), s["blood_group"])):
        remaining = int(need["units"])
        target = int(need["hospital_id"])
        for group in rank_donor_groups(need["blood_group"]):
            for entry in sorted((e for e in index.get(group, []) if e[0] != target and e[1] > 0),
                                key=lambda e: (distance_km(e[0], target), e[0])):
                if remaining == 0:
                    break
                take = min(remaining, entry[1])
                entry[1] -= take
                remaining -= take
                matches.append({"from_hospital_id": entry[0], "to_hospital_id": target, "unit_group": group,
                                "needed_group": need["blood_group"], "units": take,
                                "exact": group == need["blood_group"],
                                "distance_km": round(distance_km(entry[0], target), 2)})
            if remaining == 0:
                break
        if remaining:
            unmet.append({"hospital_id": target, "blood_group": need["blood_group"], "units": remaining})
    return {"matches": matches, "unmet": unmet}
