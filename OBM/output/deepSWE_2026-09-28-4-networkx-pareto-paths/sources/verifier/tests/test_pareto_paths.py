"""F2P：networkx 多目标帕累托最优路径（nx.pareto_paths）行为验收。

判分口径：这些用例在基线（networkx 无 pareto_paths）上必然失败；
在满足公开契约的实现上必须全部通过。不与任何参考实现比对。
"""

from __future__ import annotations

import copy
import random
import time

import networkx as nx
import pytest


# --------------------------------------------------------------------------- #
# 独立的暴力枚举 oracle（仅用于小图对拍，与实现无关）
# --------------------------------------------------------------------------- #
def _dominates(c1, w1, c2, w2):
    return c1 <= c2 and w1 <= w2 and (c1 < c2 or w1 < w2)


def _oracle_frontier(G, s, t, max_cost=None, max_weight=None):
    pairs = set()

    def dfs(u, visited, c, w):
        if u == t:
            if (max_cost is None or c <= max_cost) and (
                max_weight is None or w <= max_weight
            ):
                pairs.add((c, w))
            return
        for v, d in G.adj[u].items():
            if v in visited:
                continue
            dfs(
                v,
                visited | {v},
                c + (d.get("cost", 0) or 0),
                w + (d.get("weight", 0) or 0),
            )

    dfs(s, {s}, 0, 0)
    return sorted(
        p for p in pairs if not any(_dominates(q[0], q[1], p[0], p[1]) for q in pairs)
    )


def _path_sum(G, path):
    c = w = 0
    for u, v in zip(path, path[1:]):
        d = G.adj[u][v]
        c += d.get("cost", 0) or 0
        w += d.get("weight", 0) or 0
    return c, w


def _pairs(result):
    return [(r["cost"], r["weight"]) for r in result]


def _small_graph(seed, directed=True, n=6, density=0.5):
    rng = random.Random(seed)
    G = nx.DiGraph() if directed else nx.Graph()
    G.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if directed or u < v:
                if rng.random() < density:
                    G.add_edge(
                        u,
                        v,
                        cost=rng.choice([0, 1, 2, 3, 4, 5]),
                        weight=rng.choice([0, 1, 2, 3, 4, 5]),
                    )
    return G


def _reachable_small_graph(seed, directed=True, n=6, density=0.5):
    """与 _small_graph 相同，但保证 0 -> n-1 可达（避免用例依赖随机连通性）。"""
    G = _small_graph(seed, directed=directed, n=n, density=density)
    if not nx.has_path(G, 0, n - 1):
        G.add_edge(0, n - 1, cost=1, weight=1)
    return G


# --------------------------------------------------------------------------- #
# 契约：基础语义
# --------------------------------------------------------------------------- #
def test_basic_frontier_two_objectives():
    G = nx.DiGraph()
    G.add_edge("s", "a", cost=1, weight=1)
    G.add_edge("a", "t", cost=1, weight=1)   # (2, 2)
    G.add_edge("s", "t", cost=0, weight=3)   # (0, 3)
    assert _pairs(nx.pareto_paths(G, "s", "t")) == [(0, 3), (2, 2)]


def test_dominated_pairs_excluded():
    G = nx.DiGraph()
    G.add_edge("s", "t", cost=1, weight=1)
    G.add_edge("s", "m", cost=1, weight=1)
    G.add_edge("m", "t", cost=1, weight=1)   # (2, 2) 被 (1, 1) 支配
    assert _pairs(nx.pareto_paths(G, "s", "t")) == [(1, 1)]


def test_frontier_sorted_by_cost_ascending():
    G = nx.DiGraph()
    G.add_edge("s", "a", cost=0, weight=5)
    G.add_edge("a", "t", cost=0, weight=0)   # (0, 5)
    G.add_edge("s", "b", cost=1, weight=3)
    G.add_edge("b", "t", cost=0, weight=0)   # (1, 3)
    G.add_edge("s", "c", cost=2, weight=1)
    G.add_edge("c", "t", cost=0, weight=0)   # (2, 1)
    result = nx.pareto_paths(G, "s", "t")
    assert _pairs(result) == [(0, 5), (1, 3), (2, 1)]
    # 前沿按 cost 升序时，weight 必然严格递减
    weights = [r["weight"] for r in result]
    assert weights == sorted(weights, reverse=True)


def test_identical_source_and_target():
    G = nx.DiGraph()
    G.add_edge("s", "t", cost=1, weight=1)
    assert _pairs(nx.pareto_paths(G, "s", "s")) == [(0, 0)]
    assert nx.pareto_paths(G, "s", "s")[0]["path"] == ["s"]


def test_unreachable_target_raises():
    G = nx.DiGraph()
    G.add_edge("a", "b", cost=1, weight=1)
    G.add_node("c")                          # c 存在但与 a 不连通
    with pytest.raises(nx.NetworkXNoPath):
        nx.pareto_paths(G, "a", "c")


def test_missing_source_or_target_raises():
    G = nx.DiGraph()
    G.add_edge("a", "b", cost=1, weight=1)
    with pytest.raises(nx.NodeNotFound):
        nx.pareto_paths(G, "zzz", "b")


# --------------------------------------------------------------------------- #
# 契约：上界过滤
# --------------------------------------------------------------------------- #
def test_max_cost_and_max_weight_bounds():
    G = nx.DiGraph()
    G.add_edge("s", "t", cost=1, weight=9)
    G.add_edge("s", "m", cost=3, weight=1)
    G.add_edge("m", "t", cost=3, weight=1)   # (6, 2)
    assert _pairs(nx.pareto_paths(G, "s", "t", max_cost=6)) == [(1, 9), (6, 2)]
    assert _pairs(nx.pareto_paths(G, "s", "t", max_weight=4)) == [(6, 2)]
    assert _pairs(nx.pareto_paths(G, "s", "t", max_cost=0)) == []


def test_bounds_can_yield_empty_result():
    G = nx.DiGraph()
    G.add_edge("s", "t", cost=5, weight=5)
    assert nx.pareto_paths(G, "s", "t", max_cost=4) == []


# --------------------------------------------------------------------------- #
# 契约：非法输入
# --------------------------------------------------------------------------- #
def test_negative_cost_raises_valueerror():
    G = nx.DiGraph()
    G.add_edge("s", "t", cost=-1, weight=1)
    with pytest.raises(ValueError):
        nx.pareto_paths(G, "s", "t")


def test_negative_weight_raises_valueerror():
    G = nx.DiGraph()
    G.add_edge("s", "t", cost=1, weight=-2)
    with pytest.raises(ValueError):
        nx.pareto_paths(G, "s", "t")


def test_multigraph_not_supported():
    G = nx.MultiDiGraph()
    G.add_edge("s", "t", cost=1, weight=1)
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.pareto_paths(G, "s", "t")


def test_missing_edge_attributes_default_to_zero():
    G = nx.DiGraph()
    G.add_edge("s", "m")                    # 两条属性都缺省 -> 0
    G.add_edge("m", "t", cost=2, weight=0)
    assert _pairs(nx.pareto_paths(G, "s", "t")) == [(2, 0)]


# --------------------------------------------------------------------------- #
# 契约：见证路径
# --------------------------------------------------------------------------- #
def test_witness_is_simple_path():
    G = _reachable_small_graph(11, directed=True)
    for r in nx.pareto_paths(G, 0, 5):
        path = r["path"]
        assert path[0] == 0 and path[-1] == 5
        assert len(set(path)) == len(path), f"见证不是简单路径：{path}"


def test_witness_attributes_match_declared_pair():
    for seed in range(30):
        G = _small_graph(seed, directed=(seed % 2 == 0))
        s, t = 0, 5
        if not nx.has_path(G, s, t):
            continue
        for r in nx.pareto_paths(G, s, t):
            assert _path_sum(G, r["path"]) == (r["cost"], r["weight"])


# --------------------------------------------------------------------------- #
# 契约：纯函数与确定性
# --------------------------------------------------------------------------- #
def test_graph_not_mutated():
    G = _reachable_small_graph(3, directed=True)
    before_nodes = sorted(G.nodes())
    before_edges = sorted((u, v, d.get("cost"), d.get("weight")) for u, v, d in G.edges(data=True))
    snapshot = copy.deepcopy(G)
    nx.pareto_paths(G, 0, 5)
    assert sorted(G.nodes()) == before_nodes
    assert sorted((u, v, d.get("cost"), d.get("weight")) for u, v, d in G.edges(data=True)) == before_edges
    assert nx.utils.graphs_equal(G, snapshot)


def test_determinism_across_repeated_calls():
    G = _reachable_small_graph(5, directed=True)
    first = nx.pareto_paths(G, 0, 5)
    for _ in range(5):
        assert nx.pareto_paths(G, 0, 5) == first


def test_zero_cost_cycle_frontier_finite():
    G = nx.DiGraph()
    G.add_edge("s", "a", cost=0, weight=0)
    G.add_edge("a", "b", cost=0, weight=0)
    G.add_edge("b", "a", cost=0, weight=0)   # 零代价环
    G.add_edge("b", "t", cost=0, weight=1)
    G.add_edge("s", "t", cost=2, weight=0)
    result = nx.pareto_paths(G, "s", "t")
    assert _pairs(result) == [(0, 1), (2, 0)]
    assert all(len(set(r["path"])) == len(r["path"]) for r in result)


def test_undirected_graph_supported():
    G = nx.Graph()
    G.add_edge("s", "a", cost=1, weight=4)
    G.add_edge("a", "t", cost=1, weight=0)   # (2, 4)
    G.add_edge("s", "t", cost=3, weight=1)   # (3, 1)
    assert _pairs(nx.pareto_paths(G, "s", "t")) == [(2, 4), (3, 1)]


# --------------------------------------------------------------------------- #
# 契约：完整性（与暴力 oracle 对拍）
# --------------------------------------------------------------------------- #
def test_randomized_matches_brute_force_oracle():
    rng = random.Random(20260928)
    checked = 0
    for i in range(400):
        directed = rng.random() < 0.5
        G = _small_graph(1000 + i, directed=directed, n=rng.randint(3, 7))
        nodes = list(G.nodes())
        s, t = rng.choice(nodes), rng.choice(nodes)
        mc = rng.choice([None, None, 3, 6, 12])
        mw = rng.choice([None, None, 3, 6, 12])
        expected = _oracle_frontier(G, s, t, max_cost=mc, max_weight=mw)
        try:
            got = nx.pareto_paths(G, s, t, max_cost=mc, max_weight=mw)
        except nx.NetworkXNoPath:
            assert expected == [], f"seed={i} 抛 NoPath 但 oracle 有 {expected}"
            continue
        assert _pairs(got) == expected, (
            f"seed={i} 前沿不一致 expected={expected} got={_pairs(got)}; "
            f"s={s} t={t} mc={mc} mw={mw} edges={list(G.edges(data=True))}"
        )
        checked += 1
    assert checked > 200


# --------------------------------------------------------------------------- #
# 契约：规模（朴素枚举不可行）
# --------------------------------------------------------------------------- #
def test_large_graph_within_time_budget():
    rng = random.Random(4242)
    n, m = 4000, 16000
    G = nx.DiGraph()
    G.add_nodes_from(range(n))
    added = 0
    while added < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u != v and not G.has_edge(u, v):
            G.add_edge(u, v, cost=rng.randint(0, 20), weight=rng.randint(0, 20))
            added += 1
    start = time.perf_counter()
    result = nx.pareto_paths(G, 0, n - 1)
    elapsed = time.perf_counter() - start
    assert result, "大规模用例不应为空"
    assert elapsed < 30.0, f"超出时限：{elapsed:.1f}s"


# --------------------------------------------------------------------------- #
# 契约：三入口一致性（pareto_paths / pareto_frontier / ParetoIndex）
# --------------------------------------------------------------------------- #
def test_frontier_entry_point_is_projection_of_paths():
    for seed in range(14):
        G = _small_graph(200 + seed, directed=(seed % 3 != 0))
        s, t = 0, 5
        if not nx.has_path(G, s, t):
            continue
        assert list(nx.pareto_frontier(G, s, t)) == _pairs(nx.pareto_paths(G, s, t))


def test_frontier_entry_point_honours_bounds():
    G = nx.DiGraph()
    G.add_edge("s", "t", cost=1, weight=9)
    G.add_edge("s", "m", cost=3, weight=1)
    G.add_edge("m", "t", cost=3, weight=1)   # (6, 2)
    for mc, mw in [(None, None), (6, None), (None, 4), (0, 0), (5, 5)]:
        assert list(nx.pareto_frontier(G, "s", "t", max_cost=mc, max_weight=mw)) == _pairs(
            nx.pareto_paths(G, "s", "t", max_cost=mc, max_weight=mw)
        ), f"mc={mc} mw={mw}"
    assert list(nx.pareto_frontier(G, "s", "t", max_weight=4)) == [(6, 2)]


def test_frontier_entry_point_returns_sorted_pairs_only():
    G = _reachable_small_graph(21)
    fr = list(nx.pareto_frontier(G, 0, 5))
    assert fr, "应有非空前沿"
    for item in fr:
        assert not isinstance(item, dict), "frontier 不应返回见证路径记录"
        assert len(item) == 2
    assert fr == sorted(fr)


def test_frontier_entry_point_raises_like_paths():
    G = nx.DiGraph()
    G.add_edge("a", "b", cost=1, weight=1)
    G.add_node("c")
    with pytest.raises(nx.NetworkXNoPath):
        nx.pareto_frontier(G, "a", "c")
    with pytest.raises(nx.NodeNotFound):
        nx.pareto_frontier(G, "zzz", "b")


# --------------------------------------------------------------------------- #
# 契约：weight / cost 可以是可调用对象
# --------------------------------------------------------------------------- #
def test_callable_weight_and_cost_equal_attribute_names():
    for seed in range(20):
        G = _small_graph(300 + seed, directed=(seed % 2 == 0))
        s, t = 0, 5
        if not nx.has_path(G, s, t):
            continue
        by_name = _pairs(nx.pareto_paths(G, s, t, weight="weight", cost="cost"))
        by_call = _pairs(
            nx.pareto_paths(
                G, s, t,
                weight=lambda u, v, d: d.get("weight", 0),
                cost=lambda u, v, d: d.get("cost", 0),
            )
        )
        assert by_name == by_call, f"seed={seed}"

        f_name = list(nx.pareto_frontier(G, s, t))
        f_call = list(
            nx.pareto_frontier(
                G, s, t,
                weight=lambda u, v, d: d.get("weight", 0),
                cost=lambda u, v, d: d.get("cost", 0),
            )
        )
        assert f_name == f_call, f"seed={seed} frontier"


def test_callable_may_transform_attribute_values():
    G = nx.DiGraph()
    G.add_edge("s", "a", cost=1, weight=1)
    G.add_edge("a", "t", cost=1, weight=1)   # (2, 2) -> weight 翻倍 (2, 4)
    G.add_edge("s", "t", cost=3, weight=0)   # (3, 0)
    res = nx.pareto_paths(
        G, "s", "t",
        weight=lambda u, v, d: 2 * d.get("weight", 0),
        cost=lambda u, v, d: d.get("cost", 0),
    )
    assert _pairs(res) == [(2, 4), (3, 0)]


def test_callable_accepted_by_index():
    G = _index_graph()
    idx = nx.ParetoIndex(
        G, "s",
        weight=lambda u, v, d: d.get("weight", 0),
        cost=lambda u, v, d: d.get("cost", 0),
    )
    assert _pairs(idx.pareto("t")) == _pairs(nx.pareto_paths(G, "s", "t"))
    assert list(idx.frontier("t")) == list(nx.pareto_frontier(G, "s", "t"))


# --------------------------------------------------------------------------- #
# 契约：前沿集合与图的构造顺序无关
# --------------------------------------------------------------------------- #
def test_frontier_independent_of_edge_insertion_order():
    rng = random.Random(777)
    for seed in range(18):
        G = _small_graph(400 + seed, directed=True)
        s, t = 0, 5
        if not nx.has_path(G, s, t):
            continue
        edges = list(G.edges(data=True))
        rng.shuffle(edges)
        H = nx.DiGraph()
        H.add_nodes_from(G.nodes)
        for u, v, d in edges:
            H.add_edge(u, v, **d)
        assert list(nx.pareto_frontier(G, s, t)) == list(nx.pareto_frontier(H, s, t)), (
            f"seed={seed} 前沿依赖了插入顺序"
        )


# --------------------------------------------------------------------------- #
# 契约：ParetoIndex（可变图索引）
# --------------------------------------------------------------------------- #
def _index_graph():
    G = nx.DiGraph()
    G.add_edge("s", "a", cost=1, weight=4)
    G.add_edge("a", "t", cost=1, weight=0)   # (2, 4)
    G.add_edge("s", "b", cost=3, weight=1)
    G.add_edge("b", "t", cost=0, weight=0)   # (3, 1)
    return G


def test_pareto_index_exists_and_matches_function_entries():
    G = _index_graph()
    idx = nx.ParetoIndex(G, "s")
    assert _pairs(idx.pareto("t")) == _pairs(nx.pareto_paths(G, "s", "t"))
    assert list(idx.frontier("t")) == list(nx.pareto_frontier(G, "s", "t"))


def test_pareto_index_does_not_mutate_input_graph():
    G = _index_graph()
    snapshot = copy.deepcopy(G)
    idx = nx.ParetoIndex(G, "s")
    idx.update_edge("a", "t", cost=0, weight=0)
    if idx.graph.has_edge("s", "b"):
        idx.remove_edge("s", "b")
    idx.pareto("t")
    assert nx.utils.graphs_equal(G, snapshot), "构造或使用索引时改动了调用方的图"


def test_pareto_index_update_edge_is_reflected():
    G = _index_graph()
    idx = nx.ParetoIndex(G, "s")
    idx.update_edge("s", "t", cost=0, weight=9)
    assert _pairs(idx.pareto("t")) == _pairs(nx.pareto_paths(idx.graph, "s", "t"))
    assert (0, 9) in list(idx.frontier("t"))
    idx.update_edge("s", "t", cost=0, weight=1)      # 覆盖同一对端点
    assert _pairs(idx.pareto("t")) == _pairs(nx.pareto_paths(idx.graph, "s", "t"))


def test_pareto_index_remove_edge_equals_recompute():
    G = _index_graph()
    idx = nx.ParetoIndex(G, "s")
    idx.remove_edge("a", "t")
    assert list(idx.frontier("t")) == list(nx.pareto_frontier(idx.graph, "s", "t"))
    assert _pairs(idx.pareto("t")) == _pairs(nx.pareto_paths(idx.graph, "s", "t"))


def test_pareto_index_remove_missing_edge_raises():
    idx = nx.ParetoIndex(_index_graph(), "s")
    with pytest.raises(nx.NetworkXError):
        idx.remove_edge("t", "s")


def test_pareto_index_reset_restores_construction_state():
    G = _index_graph()
    before = list(nx.pareto_frontier(G, "s", "t"))
    idx = nx.ParetoIndex(G, "s")
    idx.update_edge("s", "t", cost=0, weight=0)
    idx.remove_edge("a", "t")
    idx.reset()
    assert list(idx.frontier("t")) == before
    assert _pairs(idx.pareto("t")) == _pairs(nx.pareto_paths(G, "s", "t"))


def test_pareto_index_bounds_match_function_entries():
    G = _index_graph()
    idx = nx.ParetoIndex(G, "s")
    for mc, mw in [(None, None), (2, None), (None, 1), (0, 0), (5, 5)]:
        assert list(idx.frontier("t", max_cost=mc, max_weight=mw)) == list(
            nx.pareto_frontier(idx.graph, "s", "t", max_cost=mc, max_weight=mw)
        ), f"mc={mc} mw={mw}"


def test_pareto_index_graph_reflects_mutations():
    idx = nx.ParetoIndex(_index_graph(), "s")
    idx.update_edge("x", "y", cost=1, weight=2)
    assert idx.graph.has_edge("x", "y")
    idx.remove_edge("x", "y")
    assert not idx.graph.has_edge("x", "y")


def test_pareto_index_exception_semantics():
    idx = nx.ParetoIndex(_index_graph(), "s")
    with pytest.raises(nx.NodeNotFound):
        idx.pareto("zzz")
    idx.update_edge("iso", "iso2", cost=1, weight=1)   # 与 source 不连通
    with pytest.raises(nx.NetworkXNoPath):
        idx.pareto("iso2")


def test_pareto_index_negative_value_after_update_raises():
    idx = nx.ParetoIndex(_index_graph(), "s")
    idx.update_edge("a", "t", cost=-5, weight=0)
    with pytest.raises(ValueError):
        idx.pareto("t")


def test_pareto_index_constructor_rejects_bad_input():
    M = nx.MultiDiGraph()
    M.add_edge("s", "t", cost=1, weight=1)
    with pytest.raises(nx.NetworkXNotImplemented):
        nx.ParetoIndex(M, "s")
    with pytest.raises(nx.NodeNotFound):
        nx.ParetoIndex(_index_graph(), "nope")


def test_pareto_index_randomized_matches_full_recompute():
    rng = random.Random(31337)
    checked = 0
    for i in range(25):
        G = _small_graph(700 + i, directed=True)
        if 0 not in G:
            continue
        idx = nx.ParetoIndex(G, 0)
        for _ in range(rng.randint(1, 6)):
            u = rng.choice(list(idx.graph.nodes))
            v = rng.choice(list(idx.graph.nodes))
            if rng.random() < 0.7:
                idx.update_edge(u, v, cost=rng.choice([0, 1, 2]),
                                weight=rng.choice([0, 1, 2]))
            elif idx.graph.has_edge(u, v):
                idx.remove_edge(u, v)
        t = 5 if 5 in idx.graph else rng.choice(list(idx.graph.nodes))
        if t == 0:
            continue
        try:
            expected = _pairs(nx.pareto_paths(idx.graph, 0, t))
        except nx.NetworkXNoPath:
            with pytest.raises(nx.NetworkXNoPath):
                idx.pareto(t)
            continue
        assert _pairs(idx.pareto(t)) == expected, f"i={i} 索引与全量重算不一致"
        assert list(idx.frontier(t)) == list(nx.pareto_frontier(idx.graph, 0, t))
        checked += 1
    assert checked > 10


def test_large_graph_all_entries_within_time_budget():
    rng = random.Random(99991)
    n, m = 3000, 12000
    G = nx.DiGraph()
    G.add_nodes_from(range(n))
    added = 0
    while added < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u != v and not G.has_edge(u, v):
            G.add_edge(u, v, cost=rng.randint(0, 20), weight=rng.randint(0, 20))
            added += 1
    start = time.perf_counter()
    idx = nx.ParetoIndex(G, 0)
    idx.update_edge(0, n - 1, cost=1, weight=1)
    idx.remove_edge(1, 2) if idx.graph.has_edge(1, 2) else None
    recs = idx.pareto(n - 1)
    fr = idx.frontier(n - 1)
    elapsed = time.perf_counter() - start
    assert recs, "大规模用例不应为空"
    assert list(fr) == _pairs(recs)
    assert elapsed < 30.0, f"超出时限：{elapsed:.1f}s"
