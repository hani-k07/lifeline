"""Donor segmentation with K-Means, written from scratch (deterministic: k-means++ seeding from a fixed seed).

Features (standardised): age, number of donations, days since the last donation (capped at two years).
Segments are named from the cluster centres, not from cluster numbers, so the names mean the same thing every run:
    LAPSED      the cluster that has gone longest without donating (re-engage first)
    CORE        of the rest, the most frequent donors
    OCCASIONAL  everyone else

Complexity   O(n * k * iterations * features); iterations <= max_iter
PEAS - donor engagement agent
    Performance  outreach goes to the donors most likely to respond
    Environment  the donor registry
    Actuators    a segment label per donor + a summary per segment
    Sensors      age, donation count, recency
"""
from __future__ import annotations

import math
import random
from collections.abc import Sequence
from datetime import date
from typing import Any

MAX_DAYS_SINCE = 730.0


def _distance2(a: Sequence[float], b: Sequence[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b, strict=True))


def kmeans(points: Sequence[Sequence[float]], k: int, seed: int = 42, max_iter: int = 100) -> tuple[list[int], list[list[float]]]:
    """Lloyd's algorithm with k-means++ initial centres. Returns (label per point, centres)."""
    n = len(points)
    if n == 0:
        return [], []
    k = max(1, min(k, n))
    rng = random.Random(seed)
    centres = [list(points[rng.randrange(n)])]
    while len(centres) < k:                                  # k-means++: far-away points are more likely to be picked
        d2 = [min(_distance2(p, c) for c in centres) for p in points]
        total = sum(d2)
        if total == 0:                                       # all remaining points coincide with a centre
            centres.append(list(points[rng.randrange(n)]))
            continue
        pick, acc = rng.random() * total, 0.0
        for point, weight in zip(points, d2, strict=True):
            acc += weight
            if acc >= pick:
                centres.append(list(point))
                break
    labels = [-1] * n
    for _ in range(max_iter):
        new = [min(range(k), key=lambda c: (_distance2(p, centres[c]), c)) for p in points]
        if new == labels:
            break
        labels = new
        for c in range(k):
            members = [points[i] for i in range(n) if labels[i] == c]
            if members:
                centres[c] = [sum(col) / len(members) for col in zip(*members, strict=True)]
    return labels, centres


def _days_since(last: Any, today: date) -> float:
    if not last:
        return MAX_DAYS_SINCE
    return float(min(MAX_DAYS_SINCE, max(0, (today - date.fromisoformat(str(last)[:10])).days)))


def segment_donors(donors: Sequence[dict[str, Any]], today: date, k: int = 3, seed: int = 42) -> dict[str, Any]:
    """Cluster donors and name each segment. Donors need id/name and optionally age, times_donated, last_donated."""
    if not donors:
        return {"segments": [], "summary": []}
    raw = [[float(d.get("age") or 30), float(d.get("times_donated") or 0), _days_since(d.get("last_donated"), today)]
           for d in donors]
    cols = list(zip(*raw, strict=True))
    means = [sum(c) / len(c) for c in cols]
    stds = [math.sqrt(sum((v - m) ** 2 for v in c) / len(c)) or 1.0 for c, m in zip(cols, means, strict=True)]
    scaled = [[(v - m) / s for v, m, s in zip(row, means, stds, strict=True)] for row in raw]
    labels, _ = kmeans(scaled, k, seed)

    clusters = sorted(set(labels))
    profile = {c: [sum(raw[i][f] for i in range(len(raw)) if labels[i] == c) / labels.count(c) for f in range(3)] for c in clusters}
    names: dict[int, str] = {}
    lapsed = max(clusters, key=lambda c: (profile[c][2], -c))
    if len(clusters) > 1 and profile[lapsed][2] > 0:
        names[lapsed] = "LAPSED"
    rest = [c for c in clusters if c not in names]
    if len(rest) > 1:
        names[max(rest, key=lambda c: (profile[c][1], -c))] = "CORE"
    for c in clusters:
        names.setdefault(c, "OCCASIONAL")

    segments = [{"donor_id": d.get("id"), "donor_name": d.get("name"), "segment": names[labels[i]]}
                for i, d in enumerate(donors)]
    summary = []
    for name in ("CORE", "OCCASIONAL", "LAPSED"):
        members = [c for c in clusters if names[c] == name]
        if not members:
            continue
        mean = [sum(profile[c][f] for c in members) / len(members) for f in range(3)]
        summary.append({"segment": name, "count": sum(1 for s in segments if s["segment"] == name),
                        "avg_age": round(mean[0], 1), "avg_donations": round(mean[1], 1), "avg_days_since_last": round(mean[2])})
    return {"segments": segments, "summary": summary}
