"""Ordering blood units and deadlines.

FEFO (First-Expired-First-Out) dispatch
    Algorithm    min-heap on (expiry date, id); expired units are set aside, never dispatched
    Complexity   O(n log n) time, O(n) space

Merge sort (stable, top-down)
    Algorithm    divide and conquer; equal keys keep their original order
    Complexity   O(n log n) time in every case, O(n) space

PEAS - stock rotation agent
    Performance  units that expire first leave first, so nothing is wasted while fresher stock sits unused
    Environment  a hospital's available units
    Actuators    a dispatch queue and an "expiring soon" list
    Sensors      each unit's expiry date and today's date
"""
from __future__ import annotations

import heapq
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class FefoResult:
    dispatch_order: list[dict[str, Any]]      # unexpired units, earliest expiry first
    expired: list[dict[str, Any]]             # already past expiry: must not be dispatched
    expiring_soon: list[dict[str, Any]]       # unexpired but expiring within `soon_days`


def _as_date(value: Any) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def fefo_sort(units: Sequence[dict[str, Any]], today: date | str, soon_days: int = 3) -> FefoResult:
    """Order units for dispatch. Each unit needs an `expiry_date` (ISO date); `id` breaks ties."""
    today_d = _as_date(today)
    limit = today_d + timedelta(days=soon_days)
    heap: list[tuple[date, int, int, dict[str, Any]]] = []
    expired: list[dict[str, Any]] = []
    for position, unit in enumerate(units):
        expiry = _as_date(unit["expiry_date"])
        if expiry < today_d:
            expired.append(unit)
        else:
            heapq.heappush(heap, (expiry, int(unit.get("id", 0)), position, unit))
    ordered = [heapq.heappop(heap)[3] for _ in range(len(heap))]
    soon = [u for u in ordered if _as_date(u["expiry_date"]) <= limit]
    return FefoResult(ordered, expired, soon)


def merge_sort(items: Sequence[T], key: Callable[[T], Any] = lambda x: x, reverse: bool = False) -> list[T]:
    """Stable merge sort. `reverse=True` sorts descending and still keeps equal keys in their original order."""

    def take_left(a: T, b: T) -> bool:
        ka, kb = key(a), key(b)
        return ka >= kb if reverse else ka <= kb

    def sort(part: list[T]) -> list[T]:
        if len(part) <= 1:
            return part
        mid = len(part) // 2
        left, right = sort(part[:mid]), sort(part[mid:])
        merged: list[T] = []
        i = j = 0
        while i < len(left) and j < len(right):
            if take_left(left[i], right[j]):
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                j += 1
        merged.extend(left[i:])
        merged.extend(right[j:])
        return merged

    return sort(list(items))
