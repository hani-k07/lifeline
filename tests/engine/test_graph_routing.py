import itertools
import math
import random

import pytest

from lifeline.constants import BLOOD_GROUPS
from lifeline.engine import routing
from lifeline.engine.graph import Graph, Node, build_road_graph, eta_minutes, haversine_km
from scripts.seed_demo import HOSPITALS

NODES = [Node(h[0], h[1], h[3], h[4]) for h in HOSPITALS]


def textbook() -> Graph:
    g = Graph()
    for i, name in enumerate("ABCDE", start=1):
        g.add_node(Node(i, name, 0.0, float(i)))
    for a, b, w in [(1, 2, 1), (2, 3, 2), (1, 3, 5), (3, 4, 1), (2, 4, 7)]:
        g.add_edge(a, b, w)
    return g                                     # node 5 is isolated


def test_haversine_known_distance():
    assert haversine_km(31.5716, 74.3159, 31.5716, 74.3159) == 0
    assert haversine_km(0, 0, 0, 1) == pytest.approx(111.19, abs=0.1)              # one degree of longitude at the equator
    assert 4 < haversine_km(31.5716, 74.3159, 31.5360, 74.3360) < 6                # Mayo -> Services, a few km


def test_dijkstra_takes_the_shorter_two_hop_route():
    dist, prev = textbook().dijkstra(1)
    assert dist == {1: 0.0, 2: 1.0, 3: 3.0, 4: 4.0}
    assert Graph.path(prev, 4) == [1, 2, 3, 4]                     # not the direct 1-3 edge of length 5
    assert Graph.path(prev, 5) == []                               # unreachable
    assert 5 not in dist


def test_dijkstra_matches_floyd_warshall_on_random_graphs():
    rng = random.Random(7)
    for _ in range(25):
        n = rng.randint(3, 9)
        g = Graph()
        for i in range(n):
            g.add_node(Node(i, str(i), 0, 0))
        inf = math.inf
        matrix = [[0 if i == j else inf for j in range(n)] for i in range(n)]
        for a, b in itertools.combinations(range(n), 2):
            if rng.random() < 0.5:
                w = rng.randint(1, 20)
                g.add_edge(a, b, w)
                matrix[a][b] = matrix[b][a] = w
        for k, i, j in itertools.product(range(n), repeat=3):
            matrix[i][j] = min(matrix[i][j], matrix[i][k] + matrix[k][j])
        for source in range(n):
            dist, _ = g.dijkstra(source)
            for target in range(n):
                assert dist.get(target, inf) == matrix[source][target]


def test_graph_validation():
    g = Graph()
    g.add_node(Node(1, "a", 0, 0))
    g.add_node(Node(2, "b", 0, 1))
    with pytest.raises(ValueError):
        g.add_node(Node(1, "dup", 0, 0))
    with pytest.raises(ValueError):
        g.add_edge(1, 3, 1)
    with pytest.raises(ValueError):
        g.add_edge(1, 1, 1)
    with pytest.raises(ValueError):
        g.add_edge(1, 2, -1)
    g.add_edge(1, 2, 5)
    g.add_edge(2, 1, 3)                                             # a shorter parallel edge wins
    assert g.edges() == [(1, 2, 3)]
    with pytest.raises(KeyError):
        g.dijkstra(99)
    with pytest.raises(KeyError):
        g.bfs(99)


def test_bfs_is_hop_ordered_and_respects_exclusions():
    g = textbook()
    assert g.bfs(1) == [(2, 1), (3, 1), (4, 2)]
    assert g.bfs(1, exclude={3}) == [(2, 1), (4, 2)]               # 4 is still reachable through 2
    assert g.bfs(1, exclude={2, 3}) == []


def test_components():
    assert [sorted(c) for c in textbook().components()] == [[1, 2, 3, 4], [5]]


def test_road_graph_is_sparse_connected_and_has_real_routes():
    g = build_road_graph(NODES, k=3)
    n = len(NODES)
    assert len(g.components()) == 1
    assert n - 1 <= len(g.edges()) < n * (n - 1) // 2               # sparse, unlike the old complete graph
    assert all(len(g.adj[i]) >= 3 for i in g.nodes)
    multi_hop = [len(Graph.path(g.dijkstra(a)[1], b)) - 1 for a, b in itertools.permutations(g.nodes, 2)]
    assert max(multi_hop) >= 2                                      # indirect routes exist, so BFS/Dijkstra mean something
    assert all(w >= haversine_km(g.nodes[a].lat, g.nodes[a].lon, g.nodes[b].lat, g.nodes[b].lon) for a, b, w in g.edges())


def test_road_factor_scales_distances_and_is_validated():
    a = build_road_graph(NODES, k=3, road_factor=1.0).edges()
    b = build_road_graph(NODES, k=3, road_factor=1.3).edges()
    assert [(x[0], x[1]) for x in a] == [(x[0], x[1]) for x in b]
    assert all(y[2] == pytest.approx(x[2] * 1.3) for x, y in zip(a, b, strict=True))
    with pytest.raises(ValueError):
        build_road_graph(NODES, k=0)
    with pytest.raises(ValueError):
        build_road_graph(NODES, road_factor=0.9)


def test_far_apart_clusters_are_bridged():
    nodes = [Node(1, "a", 31.50, 74.30), Node(2, "b", 31.51, 74.31), Node(3, "c", 31.52, 74.30),
             Node(4, "far1", 33.70, 73.00), Node(5, "far2", 33.71, 73.01), Node(6, "far3", 33.72, 73.00)]
    g = build_road_graph(nodes, k=2)
    assert len(g.components()) == 1
    assert any(a <= 3 < b for a, b, _ in g.edges())                # exactly the kind of link that was added


def test_eta_matches_the_documented_speed():
    assert eta_minutes(5) == pytest.approx(15.0)                    # 5 km at 20 km/h


# ------------------------------------------------------------------ routing

def stock_of(**by_hospital):
    return {int(h): groups for h, groups in by_hospital.items()}


def test_exact_group_is_ranked_before_compatible_and_o_negative_last():
    g = build_road_graph(NODES)
    stock = {1: {}, 2: {"O-": 5}, 3: {"O+": 5}, 4: {"A+": 3}, 5: {"A-": 2}}
    options = routing.find_sources(g, 1, "A+", stock)
    assert [(o.unit_group, o.hospital_id) for o in options] == [("A+", 4), ("A-", 5), ("O+", 3), ("O-", 2)]
    assert options[0].exact and not any(o.exact for o in options[1:])


def test_incompatible_stock_is_never_offered():
    g = build_road_graph(NODES)
    options = routing.find_sources(g, 1, "O-", {2: {"A+": 9, "B-": 9, "AB+": 9, "O+": 9}})
    assert options == []                                            # O- patients can only receive O-


def test_within_a_group_nearest_first_and_paths_are_consistent():
    g = build_road_graph(NODES)
    stock = {h: {"B+": 4} for h in (3, 5, 7, 9)}
    options = routing.find_sources(g, 1, "B+", stock)
    assert [o.distance_km for o in options] == sorted(o.distance_km for o in options)
    for o in options:
        assert o.path[0] == 1 and o.path[-1] == o.hospital_id and o.hops == len(o.path) - 1
        assert o.eta_min == pytest.approx(o.distance_km / 20 * 60, abs=0.1)


def test_source_hospital_is_offered_first_unless_excluded_and_min_units_filters():
    g = build_road_graph(NODES)
    stock = {1: {"A+": 2}, 2: {"A+": 1}}
    with_local = routing.find_sources(g, 1, "A+", stock)
    assert with_local[0].hospital_id == 1 and with_local[0].distance_km == 0 and with_local[0].path == (1,)
    assert [o.hospital_id for o in routing.find_sources(g, 1, "A+", stock, include_source=False)] == [2]
    assert [o.hospital_id for o in routing.find_sources(g, 1, "A+", stock, min_units=2)] == [1]
    with pytest.raises(ValueError):
        routing.find_sources(g, 1, "A+", stock, min_units=0)


def test_dijkstra_runs_exactly_once(monkeypatch):
    g = build_road_graph(NODES)
    calls = []
    original = Graph.dijkstra
    monkeypatch.setattr(Graph, "dijkstra", lambda self, s: calls.append(s) or original(self, s))
    routing.find_sources(g, 1, "A+", {h: {"A+": 1, "O-": 1} for h in range(1, 11)})
    assert calls == [1]                                              # the old code ran it once per candidate hospital


def test_every_patient_group_gets_options_from_a_fully_stocked_network():
    g = build_road_graph(NODES)
    full = {h: dict.fromkeys(BLOOD_GROUPS, 3) for h in range(1, 11)}
    for group in BLOOD_GROUPS:
        options = routing.find_sources(g, 4, group, full)
        assert options and options[0].exact and options[0].hospital_id == 4


def test_backup_hospitals_are_hop_ordered_with_dijkstra_distance():
    g = build_road_graph(NODES)
    backups = routing.backup_hospitals(g, 1, exclude={2})
    assert all(b["id"] != 2 and b["id"] != 1 for b in backups)
    assert [b["level"] for b in backups] == sorted(b["level"] for b in backups)
    dist = g.dijkstra(1)[0]
    assert all(b["distance_km"] == pytest.approx(dist[b["id"]], abs=0.01) for b in backups)
