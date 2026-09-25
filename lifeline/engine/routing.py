"""Where can blood come from, and how fast can it get here?

One Dijkstra run from the requesting hospital gives the road distance to every hospital; paths are then rebuilt from
the predecessor map (the old code re-ran Dijkstra once per candidate). Sources are ranked exact blood group first, then
compatible groups (see lifeline.engine.compatibility.rank_donor_groups, which keeps O- for last), nearest first within
each group.

Complexity  O((V + E) log V) for the Dijkstra run + O(V * G) to list options + O(n log n) to rank them.

PEAS - blood sourcing agent
    Performance  blood of a safe group reaches the patient quickly; universal donor stock is not wasted
    Environment  hospital road network + current unit counts per hospital and group
    Actuators    a ranked list of options and backup hospitals shown to staff
    Sensors      stock per (hospital, group), road distances
"""
from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from lifeline.engine.compatibility import rank_donor_groups
from lifeline.engine.graph import Graph, eta_minutes


@dataclass(frozen=True)
class SourceOption:
    hospital_id: int
    hospital_name: str
    unit_group: str          # the group that would actually be sent
    exact: bool              # unit_group == the patient's group
    units_available: int
    distance_km: float
    eta_min: float
    path: tuple[int, ...]
    hops: int


def find_sources(graph: Graph, source_id: int, blood_group: str, stock: Mapping[int, Mapping[str, int]], *,
                 include_source: bool = True, min_units: int = 1) -> list[SourceOption]:
    """Ranked sources for a patient of `blood_group` at hospital `source_id`.

    `stock[hospital_id][group]` is the number of available, unexpired units. With `include_source=False` the hospital
    itself is not offered (used when asking *other* hospitals for an exchange)."""
    if min_units < 1:
        raise ValueError("min_units must be at least 1")
    dist, prev = graph.dijkstra(source_id)                     # the only shortest-path computation
    donor_groups = rank_donor_groups(blood_group)
    options: list[SourceOption] = []
    for hospital_id, km in dist.items():
        if hospital_id == source_id and not include_source:
            continue
        held = stock.get(hospital_id, {})
        path = tuple(graph.path(prev, hospital_id))
        for group in donor_groups:
            units = held.get(group, 0)
            if units >= min_units:
                options.append(SourceOption(hospital_id, graph.nodes[hospital_id].name, group, group == blood_group,
                                            units, round(km, 2), round(eta_minutes(km), 1), path, len(path) - 1))
    rank = {g: i for i, g in enumerate(donor_groups)}
    options.sort(key=lambda o: (not o.exact, rank[o.unit_group], o.distance_km, o.hospital_id))
    return options


def backup_hospitals(graph: Graph, source_id: int, exclude: Collection[int] = ()) -> list[dict[str, float | int | str]]:
    """Fallback hospitals in breadth-first order (fewest hops first), with road distance from Dijkstra."""
    dist, _ = graph.dijkstra(source_id)
    return [{"id": node, "name": graph.nodes[node].name, "level": hops, "distance_km": round(dist[node], 2)}
            for node, hops in sorted(graph.bfs(source_id, exclude), key=lambda x: (x[1], dist[x[0]], x[0]))]
