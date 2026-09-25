"""Emergency request triage: a priority queue ordered by urgency, then by who has waited longest.

Algorithm    binary min-heap on (urgency rank, arrival time, id)
Complexity   push / pop O(log n); ordering n requests O(n log n)

PEAS - triage agent
    Performance  the most urgent, longest-waiting request is always handled first
    Environment  the list of open requests
    Actuators    an ordered work list (staff still decide)
    Sensors      urgency label, creation time
"""
from __future__ import annotations

import heapq
import itertools
from collections.abc import Iterable, Mapping
from typing import Any

URGENCY_RANK = {"CRITICAL": 0, "URGENT": 1, "ROUTINE": 2}


def _key(request: Mapping[str, Any]) -> tuple[int, str, int]:
    urgency = request.get("urgency")
    if urgency not in URGENCY_RANK:
        raise ValueError(f"unknown urgency {urgency!r}")
    return URGENCY_RANK[urgency], str(request.get("created_at", "")), int(request.get("id", 0))


class TriageQueue:
    def __init__(self) -> None:
        self._heap: list[tuple[tuple[int, str, int], int, Mapping[str, Any]]] = []
        self._tie = itertools.count()          # keeps equal keys in insertion order and avoids comparing dicts

    def push(self, request: Mapping[str, Any]) -> None:
        heapq.heappush(self._heap, (_key(request), next(self._tie), request))

    def pop(self) -> Mapping[str, Any]:
        if not self._heap:
            raise IndexError("triage queue is empty")
        return heapq.heappop(self._heap)[2]

    def peek(self) -> Mapping[str, Any] | None:
        return self._heap[0][2] if self._heap else None

    def __len__(self) -> int:
        return len(self._heap)


def triage_order(requests: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Requests in the order they should be handled."""
    queue = TriageQueue()
    for request in requests:
        queue.push(request)
    return [queue.pop() for _ in range(len(queue))]
