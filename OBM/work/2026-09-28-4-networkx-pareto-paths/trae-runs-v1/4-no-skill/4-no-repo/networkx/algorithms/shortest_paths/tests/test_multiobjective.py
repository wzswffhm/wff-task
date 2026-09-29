"""Tests for the multiobjective (Pareto) shortest path API."""

import random

import pytest

import networkx as nx
from networkx.utils import pairwise


# ---------------------------------------------------------------------------
# Validation helpers and a brute-force oracle
# ---------------------------------------------------------------------------


def path_totals(G, path, cost_attr="cost", weight_attr="weight"):
    total_cost = 0
    total_weight = 0
    for u, v in pairwise(path):
        data = G[u][v]
        total_cost += data.get(cost_attr, 0)
        total_weight += data.get(weight_attr, 0)
    return total_cost, total_weight


def validate_record(G, record, source, target):
    assert set(record) == {"cost", "weight", "path"}
    path = record["path"]
    assert path[0] == source
    assert path[-1] == target
    # The witness must be a simple path.
    assert len(path) == len(set(path))
    # Every consecutive pair must be an edge of G.
    for u, v in pairwise(path):
        assert v in G[u]
    # Declared totals must match the path exactly.
    total_cost, total_weight = path_totals(G, path)
    assert total_cost == record["cost"]
    assert total_weight == record["weight"]


def brute_force_pareto(G, source, target, max_cost=None, max_weight=None):
    """Reference answer via exhaustive enumeration of simple paths."""
    pairs = set()
    for path in nx.all_simple_paths(G, source, target):
        c, w = path_totals(G, path)
        if max_cost is not None and c > max_cost:
            continue
        if max_weight is not None and w > max_weight:
            continue
        pairs.add((c, w))
    front = []
    for pair in pairs:
        c, w = pair
        if any(
            (c2, w2) != pair and c2 <= c and w2 <= w
            for c2, w2 in pairs
        ):
            continue
        front.append(pair)
    return sorted(front)


def check_against_oracle(
    G, source, target, max_cost=None, max_weight=None
):
    result = nx.pareto_paths(
        G,
        source,
        target,
        max_cost=max_cost,
        max_weight=max_weight,
    )
    expected = brute_force_pareto(
        G, source, target, max_cost=max_cost, max_weight=max_weight
    )
    assert [(r["cost"], r["weight"]) for r in result] == expected
    for record in result:
        validate_record(G, record, source, target)
    # Ordering contract: cost ascending, then weight ascending; weights
    # strictly decrease as costs increase.
    for r1, r2 in pairwise(result):
        assert (r1["cost"], r1["weight"]) < (r2["cost"], r2["weight"])
    return result


# ---------------------------------------------------------------------------
# Deterministic hand-built cases
# ---------------------------------------------------------------------------


def test_basic_two_object_tradeoff():
    G = nx.DiGraph()
    G.add_edge("a", "b", cost=1, weight=4)
    G.add_edge("a", "c", cost=3, weight=2)
    G.add_edge("b", "d", cost=2, weight=2)
    G.add_edge("c", "d", cost=1, weight=2)
    result = nx.pareto_paths(G, "a", "d")
    assert [(r["cost"], r["weight"]) for r in result] == [(3, 6), (4, 4)]
    for record in result:
        validate_record(G, record, "a", "d")


def test_dominated_route_absent():
    G = nx.DiGraph()
    # Cheap-light direct route dominates the long detour in both metrics.
    G.add_edge(0, 1, cost=1, weight=1)
    G.add_edge(1, 3, cost=1, weight=1)
    G.add_edge(0, 2, cost=5, weight=5)
    G.add_edge(2, 3, cost=5, weight=5)
    result = nx.pareto_paths(G, 0, 3)
    assert [(r["cost"], r["weight"]) for r in result] == [(2, 2)]
    assert result[0]["path"] == [0, 1, 3]


def test_equal_pair_from_distinct_paths_appears_once():
    G = nx.DiGraph()
    G.add_edge("s", "a", cost=1, weight=4)
    G.add_edge("s", "b", cost=2, weight=2)
    G.add_edge("a", "t", cost=2, weight=2)
    G.add_edge("b", "t", cost=1, weight=4)
    result = nx.pareto_paths(G, "s", "t")
    assert [(r["cost"], r["weight"]) for r in result] == [(3, 6)]
    assert len(result) == 1
    validate_record(G, result[0], "s", "t")


def test_missing_attributes_count_as_zero():
    G = nx.DiGraph()
    G.add_edge(0, 1, cost=2)  # weight missing -> 0
    G.add_edge(1, 2, weight=3)  # cost missing -> 0
    G.add_edge(0, 2)  # both missing -> (0, 0), dominates
    result = nx.pareto_paths(G, 0, 2)
    assert [(r["cost"], r["weight"]) for r in result] == [(0, 0)]
    assert result[0]["path"] == [0, 2]

    # All edges without attributes give a single zero pair.
    H = nx.path_graph(4, create_using=nx.DiGraph())
    result = nx.pareto_paths(H, 0, 3)
    assert result == [{"cost": 0, "weight": 0, "path": [0, 1, 2, 3]}]


def test_custom_attribute_names():
    G = nx.DiGraph()
    G.add_edge("s", "a", price=1, time=4)
    G.add_edge("s", "b", price=3, time=2)
    G.add_edge("a", "t", price=2, time=2)
    G.add_edge("b", "t", price=1, time=2)
    result = nx.pareto_paths(G, "s", "t", weight="time", cost="price")
    assert [(r["cost"], r["weight"]) for r in result] == [(3, 6), (4, 4)]


def test_source_equals_target():
    G = nx.cycle_graph(5, create_using=nx.DiGraph())
    G.add_edge(0, 0, cost=1, weight=1)
    result = nx.pareto_paths(G, 0, 0)
    assert result == [{"cost": 0, "weight": 0, "path": [0]}]
    # Bounds do not change the source == target contract.
    result = nx.pareto_paths(G, 0, 0, max_cost=10, max_weight=10)
    assert result == [{"cost": 0, "weight": 0, "path": [0]}]


def test_node_not_found():
    G = nx.path_graph(3)
    with pytest.raises(nx.NodeNotFound):
        nx.pareto_paths(G, 99, 0)
    with pytest.raises(nx.NodeNotFound):
        nx.pareto_paths(G, 0, 99)


def test_no_path_directed():
    G = nx.DiGraph()
    G.add_edge(0, 1, cost=1, weight=1)
    G.add_edge(2, 3, cost=1, weight=1)
    with pytest.raises(nx.NetworkXNoPath):
        nx.pareto_paths(G, 0, 3)
    # Bounds must not turn an unreachable target into an empty list.
    with pytest.raises(nx.NetworkXNoPath):
        nx.pareto_paths(G, 0, 3, max_cost=100, max_weight=100)


def test_no_path_undirected():
    G = nx.Graph()
    G.add_edge(0, 1)
    G.add_edge(2, 3)
    with pytest.raises(nx.NetworkXNoPath):
        nx.pareto_paths(G, 0, 3)


def test_bounds_filter_when_reachable():
    G = nx.DiGraph()
    G.add_edge("s", "a", cost=1, weight=8)
    G.add_edge("s", "b", cost=8, weight=1)
    G.add_edge("a", "t", cost=1, weight=8)
    G.add_edge("b", "t", cost=8, weight=1)
    # Front without bounds: (2, 16) and (16, 2).
    assert [(r["cost"], r["weight"]) for r in nx.pareto_paths(G, "s", "t")] == [
        (2, 16),
        (16, 2),
    ]
    # Only the cheap-in-cost route fits max_cost.
    result = nx.pareto_paths(G, "s", "t", max_cost=2)
    assert [(r["cost"], r["weight"]) for r in result] == [(2, 16)]
    # Only the cheap-in-weight route fits max_weight.
    result = nx.pareto_paths(G, "s", "t", max_weight=2)
    assert [(r["cost"], r["weight"]) for r in result] == [(16, 2)]
    # Reachable but nothing fits both bounds: empty list, no exception.
    assert nx.pareto_paths(G, "s", "t", max_cost=1) == []
    assert nx.pareto_paths(G, "s", "t", max_weight=1) == []
    assert nx.pareto_paths(G, "s", "t", max_cost=10, max_weight=10) == []


def test_negative_attributes_raise_value_error():
    G = nx.DiGraph()
    G.add_edge(0, 1, cost=-1, weight=1)
    G.add_edge(1, 2, cost=1, weight=1)
    with pytest.raises(ValueError):
        nx.pareto_paths(G, 0, 2)

    G = nx.DiGraph()
    G.add_edge(0, 1, cost=1, weight=-1)
    G.add_edge(1, 2, cost=1, weight=1)
    with pytest.raises(ValueError):
        nx.pareto_paths(G, 0, 2)


def test_multigraph_raises_not_implemented():
    G = nx.MultiDiGraph()
    G.add_edge(0, 1, cost=1, weight=1)
    G.add_edge(1, 2, cost=1, weight=1)
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.pareto_paths(G, 0, 2)

    G = nx.MultiGraph()
    G.add_edge(0, 1, cost=1, weight=1)
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.pareto_paths(G, 0, 1)


def test_zero_cost_zero_weight_cycles_terminate():
    # A zero/zero 2-cycle on the way to t can be walked arbitrarily many
    # times; the search must still terminate with a single pair.
    G = nx.DiGraph()
    G.add_edge("s", "a", cost=1, weight=1)
    G.add_edge("a", "b", cost=0, weight=0)
    G.add_edge("b", "a", cost=0, weight=0)
    G.add_edge("b", "t", cost=2, weight=3)
    result = nx.pareto_paths(G, "s", "t")
    assert [(r["cost"], r["weight"]) for r in result] == [(3, 4)]
    validate_record(G, result[0], "s", "t")
    assert result[0]["path"].count("a") == 1
    assert result[0]["path"].count("b") == 1


def test_self_loop_zero_zero():
    G = nx.DiGraph()
    G.add_edge(0, 0, cost=0, weight=0)
    G.add_edge(0, 1, cost=1, weight=2)
    result = nx.pareto_paths(G, 0, 1)
    assert [(r["cost"], r["weight"]) for r in result] == [(1, 2)]
    assert result[0]["path"] == [0, 1]


def test_undirected_graph():
    G = nx.Graph()
    G.add_edge(0, 1, cost=1, weight=4)
    G.add_edge(0, 2, cost=4, weight=1)
    G.add_edge(1, 3, cost=4, weight=1)
    G.add_edge(2, 3, cost=1, weight=4)
    result = nx.pareto_paths(G, 0, 3)
    assert [(r["cost"], r["weight"]) for r in result] == [(5, 5)]
    assert len(result) == 1


def test_floating_point_attributes():
    G = nx.DiGraph()
    G.add_edge(0, 1, cost=0.5, weight=1.5)
    G.add_edge(1, 3, cost=1.5, weight=0.5)
    G.add_edge(0, 2, cost=1.0, weight=1.0)
    G.add_edge(2, 3, cost=1.0, weight=1.0)
    result = nx.pareto_paths(G, 0, 3)
    # (2, 2) via either route; one record.
    assert [(r["cost"], r["weight"]) for r in result] == [(2.0, 2.0)]
    validate_record(G, result[0], 0, 3)


def test_pure_function_and_determinism():
    G = nx.DiGraph()
    G.add_edge(0, 1, cost=1, weight=4)
    G.add_edge(0, 2, cost=3, weight=2)
    G.add_edge(1, 3, cost=2, weight=2)
    G.add_edge(2, 3, cost=1, weight=2)
    snapshot_nodes = set(G.nodes)
    snapshot_edges = [(u, v, dict(d)) for u, v, d in G.edges(data=True)]

    first = nx.pareto_paths(G, 0, 3)
    second = nx.pareto_paths(G, 0, 3)
    third = nx.pareto_paths(G, 0, 3, max_cost=100, max_weight=100)
    assert first == second == third

    assert set(G.nodes) == snapshot_nodes
    assert [(u, v, dict(d)) for u, v, d in G.edges(data=True)] == snapshot_edges


# ---------------------------------------------------------------------------
# Randomized differential tests against the brute-force oracle
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("directed", [True, False])
@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_random_graphs_match_oracle(directed, seed):
    rng = random.Random(seed)
    G = nx.gnp_random_graph(
        14, 0.25, seed=seed * 7 + 13, directed=directed
    )
    # Remove self loops for clarity of the random suite.
    G.remove_edges_from(nx.selfloop_edges(G))
    for u, v, data in G.edges(data=True):
        # Includes plenty of zeros to stress equal / zero-cycle handling.
        data["cost"] = rng.randrange(0, 4)
        data["weight"] = rng.randrange(0, 4)
        if rng.random() < 0.1:
            del data["cost"]
        if rng.random() < 0.1:
            del data["weight"]

    nodes = list(G.nodes)
    for _ in range(12):
        s = rng.choice(nodes)
        t = rng.choice(nodes)
        if s == t:
            assert nx.pareto_paths(G, s, t) == [
                {"cost": 0, "weight": 0, "path": [s]}
            ]
            continue
        try:
            result = check_against_oracle(G, s, t)
        except nx.NetworkXNoPath:
            assert not nx.has_path(G, s, t)
            continue
        if result:
            # Exercise bounds: tighten them to a frontier record's totals.
            mid = result[len(result) // 2]
            check_against_oracle(
                G, s, t, max_cost=mid["cost"], max_weight=mid["weight"]
            )
            # A bound below every feasible pair gives [] when reachable.
            min_c = result[0]["cost"]
            min_w = result[-1]["weight"]
            if min_c > 0:
                assert nx.pareto_paths(G, s, t, max_cost=min_c - 1) == []
            if min_w > 0:
                assert nx.pareto_paths(G, s, t, max_weight=min_w - 1) == []
