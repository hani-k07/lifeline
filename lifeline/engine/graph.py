"""Hospital road network: a sparse weighted graph, Dijkstra shortest paths and BFS.

The old network connected every hospital to every other (a complete graph), so the shortest path was always the direct
edge and BFS had nothing to explore. Real roads do not work like that. `build_road_graph` links each hospital to its
k nearest neighbours only, weighs each link by straight-line distance x a road factor, and adds bridging links if that
leaves the network in pieces - so every hospital stays reachable and multi-hop routes appear.

Algorithms
----------
Dijkstra (binary heap, lazy deletion)  time O((V + E) log V)  space O(V)
Breadth-first search                   time O(V + E)          space O(V)
k-NN construction                      time O(V^2 log V)      (V is tens of hospitals)

PEAS - routing agent
    Performance  shortest road distance / earliest arrival at a hospital that can supply blood
    Environment  road network between hospitals (static weights, no live traffic)
    Actuators    ranked routes for staff to choose from (nothing is dispatched automatically)
    Sensors      hospital coordinates and, for routing, current stock at each hospital
"""
from __future__ import annotations

import heapq
import math
from collections import deque
from collections.abc import Collection, Sequence
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0088
ROAD_FACTOR = 1.3          # road distance is about 1.3x the straight line in a dense city
AMBULANCE_KMH = 20.0       # average urban ambulance speed used for ETAs (about 3 min per km); an assumption


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def eta_minutes(km: float) -> float:
    return km / AMBULANCE_KMH * 60


@dataclass(frozen=True)
class Node:
    id: int
    name: str
    lat: float
    lon: float


class Graph:
    """Undirected weighted graph keyed by integer node id."""

    def __init__(self) -> None:
        self.nodes: dict[int, Node] = {}
        self.adj: dict[int, dict[int, float]] = {}

    def add_node(self, node: Node) -> None:
        if node.id in self.nodes:
            raise ValueError(f"duplicate node id {node.id}")
        self.nodes[node.id] = node
        self.adj[node.id] = {}

    def add_edge(self, a: int, b: int, km: float) -> None:
        if a not in self.nodes or b not in self.nodes:
            raise ValueError("edge endpoints must be existing nodes")
        if a == b:
            raise ValueError("self loops are not allowed")
        if km < 0:
            raise ValueError("edge length cannot be negative")
        km = min(km, self.adj[a].get(b, math.inf))
        self.adj[a][b] = self.adj[b][a] = km

    def edges(self) -> list[tuple[int, int, float]]:
        return sorted((a, b, w) for a, nbrs in self.adj.items() for b, w in nbrs.items() if a < b)

    def dijkstra(self, source: int) -> tuple[dict[int, float], dict[int, int | None]]:
        """Shortest distance (km) and predecessor for every node reachable from `source`."""
        if source not in self.nodes:
            raise KeyError(source)
        dist: dict[int, float] = {source: 0.0}
        prev: dict[int, int | None] = {source: None}
        heap: list[tuple[float, int]] = [(0.0, source)]
        done: set[int] = set()
        while heap:
            d, u = heapq.heappop(heap)
            if u in done:
                continue
            done.add(u)
            for v, w in self.adj[u].items():
                nd = d + w
                if nd < dist.get(v, math.inf):
                    dist[v], prev[v] = nd, u
                    heapq.heappush(heap, (nd, v))
        return dist, prev

    @staticmethod
    def path(prev: dict[int, int | None], target: int) -> list[int]:
        """Rebuild source -> target from a predecessor map; [] if `target` was not reached."""
        if target not in prev:
            return []
        out: list[int] = []
        node: int | None = target
        while node is not None:
            out.append(node)
            node = prev[node]
        return out[::-1]

    def bfs(self, source: int, exclude: Collection[int] = ()) -> list[tuple[int, int]]:
        """(node, hop count) in breadth-first order, ties broken by id. Excluded nodes are neither listed nor crossed."""
        if source not in self.nodes:
            raise KeyError(source)
        hops = {source: 0}
        queue: deque[int] = deque([source])
        out: list[tuple[int, int]] = []
        while queue:
            u = queue.popleft()
            for v in sorted(self.adj[u]):
                if v in hops or v in exclude:
                    continue
                hops[v] = hops[u] + 1
                out.append((v, hops[v]))
                queue.append(v)
        return out

    def components(self) -> list[set[int]]:
        seen: set[int] = set()
        result: list[set[int]] = []
        for start in sorted(self.nodes):
            if start in seen:
                continue
            comp = {start}
            queue = deque([start])
            while queue:
                for v in self.adj[queue.popleft()]:
                    if v not in comp:
                        comp.add(v)
                        queue.append(v)
            seen |= comp
            result.append(comp)
        return result


def build_road_graph(nodes: Sequence[Node], k: int = 3, road_factor: float = ROAD_FACTOR) -> Graph:
    """Sparse road network: each node linked to its k nearest, then bridged until fully connected."""
    if k < 1:
        raise ValueError("k must be at least 1")
    if road_factor < 1:
        raise ValueError("road_factor cannot be below 1 (roads are never shorter than the straight line)")
    graph = Graph()
    for node in nodes:
        graph.add_node(node)

    def km(a: Node, b: Node) -> float:
        return haversine_km(a.lat, a.lon, b.lat, b.lon) * road_factor

    ordered = sorted(nodes, key=lambda n: n.id)
    for node in ordered:
        nearest = sorted((o for o in ordered if o.id != node.id), key=lambda o: (km(node, o), o.id))[:k]
        for other in nearest:
            graph.add_edge(node.id, other.id, km(node, other))

    comps = graph.components()
    while len(comps) > 1:                      # join the closest pair of pieces until one piece is left
        best = min((km(graph.nodes[a], graph.nodes[b]), a, b) for a in comps[0] for other in comps[1:] for b in other)
        graph.add_edge(best[1], best[2], best[0])
        comps = graph.components()
    return graph
