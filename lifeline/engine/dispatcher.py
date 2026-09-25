"""run_engine(operation, payload): one validated entry point to every engine operation.

Payloads and results are plain JSON-style dicts. Any malformed input raises EngineError (never a bare KeyError or a
silently wrong answer). `OPERATIONS` carries the summary, complexity and PEAS description of each operation.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from datetime import date
from typing import Any

from lifeline.engine import clustering, forecasting, matching, routing, screening, sorting, transfusion, triage
from lifeline.engine.base import OPERATIONS, EngineError, Operation, Peas, need, number, register
from lifeline.engine.graph import Graph, Node, build_road_graph


def _graph(payload: Mapping[str, Any]) -> Graph:
    """nodes [{id, name, latitude, longitude}], optional edges [{from, to, weight}]; without edges a sparse road graph
    (k nearest neighbours, default 3) is built."""
    raw = need(payload, "nodes", list)
    if not raw:
        raise EngineError("nodes must not be empty")
    try:
        nodes = [Node(int(n["id"]), str(n.get("name", n["id"])), float(n["latitude"]), float(n["longitude"])) for n in raw]
    except (KeyError, TypeError, ValueError) as exc:
        raise EngineError(f"each node needs id, latitude and longitude ({exc})") from exc
    if len({n.id for n in nodes}) != len(nodes):
        raise EngineError("node ids must be unique")
    if "edges" not in payload:
        return build_road_graph(nodes, k=int(number(payload.get("k", 3), "k", minimum=1)),
                                road_factor=number(payload.get("road_factor", 1.3), "road_factor", minimum=1))
    graph = Graph()
    for node in nodes:
        graph.add_node(node)
    try:
        for e in need(payload, "edges", list):
            graph.add_edge(int(e["from"]), int(e["to"]), number(e["weight"], "edge weight", minimum=0))
    except (KeyError, ValueError) as exc:
        raise EngineError(f"invalid edge ({exc})") from exc
    return graph


def _source(payload: Mapping[str, Any], graph: Graph) -> int:
    source = int(need(payload, "source_id", int))
    if source not in graph.nodes:
        raise EngineError(f"source_id {source} is not one of the nodes")
    return source


@register("dijkstra", summary="Shortest road distance and path from one hospital to the others",
          complexity="O((V + E) log V)", used_by="Emergency, Exchange, Analytics",
          peas=Peas("shortest road distance", "sparse hospital road network", "distance table and paths", "coordinates"))
def _op_dijkstra(payload: Mapping[str, Any]) -> dict[str, Any]:
    graph = _graph(payload)
    source = _source(payload, graph)
    dist, prev = graph.dijkstra(source)
    targets = payload.get("targets") or [n for n in dist if n != source]
    return {"distances": {n: round(d, 2) for n, d in dist.items()},
            "paths": {int(t): graph.path(prev, int(t)) for t in targets}}


@register("bfs_backup", summary="Backup hospitals in fewest-hops order",
          complexity="O(V + E)", used_by="Emergency (backup options)",
          peas=Peas("nearest fallbacks by hop count", "road network", "ranked fallback hospitals", "network structure"))
def _op_bfs(payload: Mapping[str, Any]) -> dict[str, Any]:
    graph = _graph(payload)
    return {"backup_hospitals": routing.backup_hospitals(graph, _source(payload, graph),
                                                         {int(x) for x in payload.get("exclude_ids", [])})}


@register("find_sources", summary="Ranked blood sources: exact group first, then compatible groups, nearest first",
          complexity="O((V + E) log V + V*G)", used_by="Emergency, Exchange",
          peas=Peas("safe blood arrives fast, O- spared", "network + stock", "ranked options", "stock, distances"))
def _op_find_sources(payload: Mapping[str, Any]) -> dict[str, Any]:
    graph = _graph(payload)
    stock = {int(h): {str(g): int(n) for g, n in groups.items()} for h, groups in need(payload, "stock", dict).items()}
    options = routing.find_sources(graph, _source(payload, graph), str(need(payload, "blood_group", str)), stock,
                                   include_source=bool(payload.get("include_source", True)),
                                   min_units=int(number(payload.get("min_units", 1), "min_units", minimum=1)))
    return {"options": [dataclasses.asdict(o) for o in options]}


@register("fefo_sort", summary="Dispatch order by earliest expiry; expired units set aside",
          complexity="O(n log n)", used_by="Inventory",
          peas=Peas("nothing expires while fresher stock is used", "available units", "dispatch queue", "expiry dates"))
def _op_fefo(payload: Mapping[str, Any]) -> dict[str, Any]:
    units = need(payload, "units", list)
    today = str(need(payload, "today", str))
    try:
        result = sorting.fefo_sort(units, today, int(number(payload.get("soon_days", 3), "soon_days", minimum=0)))
    except (KeyError, ValueError) as exc:
        raise EngineError(f"each unit needs a valid expiry_date ({exc})") from exc
    return {"dispatch_order": result.dispatch_order, "expired": result.expired, "expiring_soon": result.expiring_soon}


@register("merge_sort", summary="Stable sort of records by a field",
          complexity="O(n log n)", used_by="Contracts (loans by deadline)",
          peas=Peas("chronological order", "a list of records", "sorted list", "the key field"))
def _op_merge_sort(payload: Mapping[str, Any]) -> dict[str, Any]:
    items = need(payload, "items", list)
    key = str(need(payload, "key", str))
    try:
        for record in items:                     # a one-item list is never compared, so check the key on every record up front
            record[key]
        return {"sorted": sorting.merge_sort(items, key=lambda r: r[key], reverse=bool(payload.get("reverse", False)))}
    except (KeyError, TypeError) as exc:
        raise EngineError(f"every item needs a comparable {key!r} ({exc})") from exc


@register("exchange_match", summary="Suggest transfers that cover shortages from surpluses",
          complexity="O(S + D*G*C log C)", used_by="Exchange (suggestions)",
          peas=Peas("shortages covered from nearby surplus", "per-hospital stock vs thresholds", "suggested transfers", "stock, distances"))
def _op_exchange_match(payload: Mapping[str, Any]) -> dict[str, Any]:
    graph = _graph(payload)
    cache: dict[int, dict[int, float]] = {}

    def distance(a: int, b: int) -> float:
        if a not in cache:
            cache[a] = graph.dijkstra(a)[0]
        return cache[a].get(b, float("inf"))

    return matching.exchange_match(need(payload, "shortages", list), need(payload, "surpluses", list), distance)


@register("screen_donor", summary="Donor eligibility: every rule evaluated, every fired rule reported",
          complexity="O(r)", used_by="Screening",
          peas=Peas("no unsafe donor cleared", "one donor's intake data", "SAFE/DEFER/BLOCK + reasons", "serology, vitals, history"))
def _op_screen(payload: Mapping[str, Any]) -> dict[str, Any]:
    return screening.screen_donor(need(payload, "donor", dict))


@register("risk_score", summary="0-100 donor safety score from the same rules",
          complexity="O(r)", used_by="Screening",
          peas=Peas("score never contradicts the decision", "one donor's intake data", "score + penalties", "serology, vitals, history"))
def _op_risk(payload: Mapping[str, Any]) -> dict[str, Any]:
    return screening.risk_score(need(payload, "donor", dict))


@register("transfusion_monitor", summary="Reaction check on pre/post vitals; missing data is UNKNOWN, never normal",
          complexity="O(r)", used_by="Transfusion",
          peas=Peas("no reaction reported as normal", "one transfusion", "severity + action", "temperature, BP, pulse, SpO2"))
def _op_monitor(payload: Mapping[str, Any]) -> dict[str, Any]:
    return transfusion.monitor_reaction(need(payload, "pre", dict), need(payload, "post", dict))


@register("fuzzy_severity", summary="Graded 0-100 severity from fuzzy memberships",
          complexity="O(1)", used_by="Transfusion (supplementary score)",
          peas=Peas("graded severity", "vital-sign changes", "score + label", "temperature, BP, SpO2, pulse changes"))
def _op_fuzzy(payload: Mapping[str, Any]) -> dict[str, Any]:
    return transfusion.fuzzy_severity(*(number(payload.get(k, 0), k) for k in ("temp_rise", "bp_drop", "o2_drop", "pulse_rise")))


@register("predict_shortage", summary="Per blood group: forecast, days to stock-out, risk and reorder quantity",
          complexity="O(G * (window * horizon + n))", used_by="Analytics, AI Center",
          peas=Peas("shortage flagged early", "usage history + stock", "risk level + reorder", "daily usage"))
def _op_predict(payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = forecasting.predict_shortage(need(payload, "groups", list), int(number(payload.get("horizon", 7), "horizon", minimum=1)),
                                        int(number(payload.get("window", 7), "window", minimum=1)),
                                        number(payload.get("buffer", 1.5), "buffer", minimum=1))
    return {"predictions": rows}


@register("cluster_donors", summary="K-Means donor segments: CORE / OCCASIONAL / LAPSED",
          complexity="O(n*k*iterations)", used_by="Analytics (donors)",
          peas=Peas("outreach to the right donors", "donor registry", "segment per donor", "age, donations, recency"))
def _op_cluster(payload: Mapping[str, Any]) -> dict[str, Any]:
    today = date.fromisoformat(str(need(payload, "today", str)))
    return clustering.segment_donors(need(payload, "donors", list), today, int(number(payload.get("k", 3), "k", minimum=1)),
                                     int(number(payload.get("seed", 42), "seed")))


@register("triage_order", summary="Open requests ordered by urgency, then waiting time",
          complexity="O(n log n)", used_by="Emergency (queue)",
          peas=Peas("most urgent handled first", "open requests", "work list", "urgency, created_at"))
def _op_triage(payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return {"ordered": triage.triage_order(need(payload, "requests", list))}
    except ValueError as exc:
        raise EngineError(str(exc)) from exc


def run_engine(operation: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Run a registered operation. Raises EngineError for an unknown operation or invalid input."""
    op = OPERATIONS.get(operation)
    if op is None:
        raise EngineError(f"unknown operation {operation!r}; available: {', '.join(sorted(OPERATIONS))}")
    if not isinstance(payload, Mapping):
        raise EngineError("payload must be a mapping")
    try:
        return op.func(payload)
    except EngineError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise EngineError(f"{operation}: invalid input ({type(exc).__name__}: {exc})") from exc


def describe() -> list[Operation]:
    return [OPERATIONS[name] for name in sorted(OPERATIONS)]
