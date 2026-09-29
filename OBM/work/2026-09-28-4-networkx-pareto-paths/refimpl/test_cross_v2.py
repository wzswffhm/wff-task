"""v2 契约自证：暴力 oracle + 差分测试。

用法（Windows 托管 python，PYTHONPATH 指向本目录 + networkx）：
    PYTHONPATH=<nx>;<refimpl> python test_cross_v2.py [轮数]
"""
import random
import sys
from itertools import permutations

import networkx as nx
from pareto_paths import ParetoIndex, pareto_frontier, pareto_paths


def brute(G, s, t, wn, cn):
    """暴力枚举全部简单路径 → 非支配 (cost, weight) 集合。"""
    pairs = {}
    mids = [n for n in G.nodes if n not in (s, t)]
    for r in range(0, len(mids) + 1):
        for combo in permutations(mids, r):
            seq = [s, *combo, t]
            if not all(G.has_edge(seq[i], seq[i + 1]) for i in range(len(seq) - 1)):
                continue
            c = sum(G[seq[i]][seq[i + 1]].get(cn, 0) for i in range(len(seq) - 1))
            w = sum(G[seq[i]][seq[i + 1]].get(wn, 0) for i in range(len(seq) - 1))
            pairs.setdefault((c, w), []).append(tuple(seq))
    feasible = set(pairs)
    front = {p for p in feasible
             if not any(q != p and q[0] <= p[0] and q[1] <= p[1] for q in feasible)}
    return front


def check_witnesses(G, s, t, records, wn, cn):
    for rec in records:
        p = list(rec["path"])
        assert p[0] == s and p[-1] == t, f"endpoints: {p}"
        assert len(set(p)) == len(p), f"not simple: {p}"
        c = sum(G[p[i]][p[i + 1]].get(cn, 0) for i in range(len(p) - 1))
        w = sum(G[p[i]][p[i + 1]].get(wn, 0) for i in range(len(p) - 1))
        assert (c, w) == (rec["cost"], rec["weight"]), f"sum mismatch {p} {c},{w}"


def rand_graph(rng, n, p, directed=True):
    G = nx.DiGraph() if directed else nx.Graph()
    G.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if not directed and v < u:
                continue
            if rng.random() < p:
                G.add_edge(u, v, cost=rng.choice([0, 0, 1, 1, 2, 3]),
                           weight=rng.choice([0, 0, 1, 1, 2, 3]))
    return G


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    rng = random.Random(20260928)
    bad = 0

    # ---- A. 暴力 oracle 对拍（前沿 + 见证 + 投影一致） ----
    tested = 0
    for i in range(rounds):
        n = rng.randint(4, 8)
        G = rand_graph(rng, n, rng.choice([0.35, 0.5, 0.65]), rng.random() < 0.7)
        s, t = rng.choice(list(G.nodes)), rng.choice(list(G.nodes))
        if s == t:
            continue                      # 契约对 s==t 有专门定义，A 组不适用
        front = brute(G, s, t, "weight", "cost")
        if not front:
            continue
        tested += 1
        try:
            recs = pareto_paths(G, s, t)
            fr = pareto_frontier(G, s, t)
        except Exception as e:                                  # noqa: BLE001
            bad += 1
            print(f"  [A{i}] RAISE {type(e).__name__}: {e}")
            continue
        got_pairs = [(r["cost"], r["weight"]) for r in recs]
        if set(got_pairs) != front or got_pairs != sorted(got_pairs):
            bad += 1
            if bad <= 5:
                print(f"  [A{i}] FRONTIER DIFF got={got_pairs} exp={sorted(front)}")
            continue
        if list(fr) != got_pairs:
            bad += 1
            print(f"  [A{i}] PROJECTION DIFF frontier={fr} paths={got_pairs}")
            continue
        try:
            check_witnesses(G, s, t, recs, "weight", "cost")
        except AssertionError as e:
            bad += 1
            if bad <= 5:
                print(f"  [A{i}] WITNESS {e}")
        if i % 100 == 0:
            print(f"  ... A 组进度 {i}/{rounds}（有效 {tested}，失败 {bad}）")

    # ---- B. 上界过滤与投影一致 ----
    for i in range(80):
        G = rand_graph(rng, rng.randint(4, 7), 0.55, True)
        s, t = 0, rng.randint(1, 6)
        if s not in G or t not in G:
            continue
        mc, mw = rng.choice([0, 1, 2, 4, None]), rng.choice([0, 1, 2, 4, None])
        try:
            a = [(r["cost"], r["weight"]) for r in
                 pareto_paths(G, s, t, max_cost=mc, max_weight=mw)]
            b = list(pareto_frontier(G, s, t, max_cost=mc, max_weight=mw))
        except nx.NetworkXNoPath:
            continue
        if a != b:
            bad += 1
            print(f"  [B{i}] BOUNDED PROJECTION DIFF {a} vs {b}")

    # ---- C. 可调用 weight / cost 与属性名等价 ----
    for i in range(60):
        G = rand_graph(rng, rng.randint(4, 7), 0.6, True)
        s, t = 0, rng.randint(1, 6)
        if s not in G or t not in G:
            continue
        def wf(u, v, d):
            return d.get("weight", 0)

        def cf(u, v, d):
            return d.get("cost", 0)

        try:
            a = [(r["cost"], r["weight"]) for r in
                 pareto_paths(G, s, t, weight="weight", cost="cost")]
            b = [(r["cost"], r["weight"]) for r in
                 pareto_paths(G, s, t, weight=wf, cost=cf)]
        except nx.NetworkXNoPath:
            continue
        if a != b:
            bad += 1
            print(f"  [C{i}] CALLABLE DIFF {a} vs {b}")

    # ---- D. 前沿集合与边插入顺序无关 ----
    for i in range(60):
        G = rand_graph(rng, rng.randint(4, 8), 0.5, True)
        s, t = 0, rng.randint(1, 7)
        if s not in G or t not in G:
            continue
        edges = list(G.edges(data=True))
        rng.shuffle(edges)
        H = type(G)()
        H.add_nodes_from(G.nodes)
        for u, v, d in edges:
            H.add_edge(u, v, **d)
        try:
            a = list(pareto_frontier(G, s, t))
            b = list(pareto_frontier(H, s, t))
        except nx.NetworkXNoPath:
            continue
        if a != b:
            bad += 1
            print(f"  [D{i}] ORDER DIFF {a} vs {b}")

    # ---- E. ParetoIndex 差分：随机变更序列后必须等于全量重算 ----
    for i in range(60):
        G = rand_graph(rng, rng.randint(5, 8), 0.5, True)
        s = 0
        if s not in G:
            continue
        before = sorted(G.edges(data=True))
        try:
            idx = ParetoIndex(G, s)
        except Exception as e:                                  # noqa: BLE001
            bad += 1
            print(f"  [E{i}] INDEX CTOR RAISE {type(e).__name__}")
            continue
        live = sorted(G.edges(data=True))
        if live != before:
            bad += 1
            print(f"  [E{i}] PURITY VIOLATION（构造索引改动了传入图）")
        for _ in range(rng.randint(1, 8)):
            op = rng.choice(["upd", "upd", "del"])
            u, v = rng.choice(list(idx.graph.nodes)), rng.choice(list(idx.graph.nodes))
            if op == "upd":
                idx.update_edge(u, v, cost=rng.choice([0, 1, 2]), weight=rng.choice([0, 1, 2]))
            else:
                if idx.graph.has_edge(u, v):
                    idx.remove_edge(u, v)
            t = rng.choice(list(idx.graph.nodes))
            if t == s:
                continue
            mc, mw = rng.choice([None, 0, 2, 5]), rng.choice([None, 0, 2, 5])

            def run(fn):
                try:
                    return "OK", list(fn())
                except nx.NetworkXNoPath:
                    return "NOPATH", None

            kind_e, exp = run(lambda: pareto_frontier(idx.graph, s, t, max_cost=mc, max_weight=mw))
            kind_g, got = run(lambda: idx.frontier(t, max_cost=mc, max_weight=mw))
            if kind_e != kind_g or got != exp:
                bad += 1
                print(f"  [E{i}] INDEX FRONTIER DIFF {kind_g},{got} vs {kind_e},{exp}")
                break
            kind_e2, exp2 = run(lambda: pareto_paths(idx.graph, s, t, max_cost=mc, max_weight=mw))
            kind_g2, got2 = run(lambda: idx.pareto(t, max_cost=mc, max_weight=mw))
            pairs_g = None if got2 is None else [(r["cost"], r["weight"]) for r in got2]
            pairs_e = None if exp2 is None else [(r["cost"], r["weight"]) for r in exp2]
            if kind_e2 != kind_g2 or pairs_g != pairs_e:
                bad += 1
                print(f"  [E{i}] INDEX PATHS DIFF {kind_g2},{pairs_g} vs {kind_e2},{pairs_e}")
                break
        # reset 必须回到构造时状态
        try:
            idx.reset()
            for t in list(idx.graph.nodes):
                if t == s:
                    continue
                k1, a = run(lambda: idx.frontier(t))
                k2, b = run(lambda: pareto_frontier(G, s, t))
                if k1 != k2 or a != b:
                    bad += 1
                    print(f"  [E{i}] RESET DIFF")
                    break
        except Exception as e:                                  # noqa: BLE001
            bad += 1
            print(f"  [E{i}] RESET RAISE {type(e).__name__}: {e}")

    # ---- F. 边界与异常语义 ----
    def expect(label, fn, exc):
        try:
            fn()
        except exc:
            return
        except Exception as e:                                  # noqa: BLE001
            print(f"  [F] {label}: 期望 {exc.__name__}，实得 {type(e).__name__}")
        else:
            print(f"  [F] {label}: 期望 {exc.__name__}，实得无异常")
        nonlocal bad
        bad += 1

    G = nx.DiGraph()
    G.add_edge("s", "t", cost=1, weight=1)
    G.add_node("z")
    expect("unreachable", lambda: pareto_paths(G, "s", "z"), nx.NetworkXNoPath)
    expect("missing node", lambda: pareto_paths(G, "nope", "t"), nx.NodeNotFound)
    M = nx.MultiDiGraph()
    M.add_edge("s", "t", cost=1, weight=1)
    expect("multigraph", lambda: pareto_paths(M, "s", "t"), nx.NetworkXNotImplemented)
    expect("index multigraph", lambda: ParetoIndex(M, "s"), nx.NetworkXNotImplemented)
    N = nx.DiGraph()
    N.add_edge("s", "t", cost=-1, weight=1)
    expect("negative", lambda: pareto_paths(N, "s", "t"), ValueError)
    idx = ParetoIndex(G, "s")
    expect("remove missing edge", lambda: idx.remove_edge("t", "s"), nx.NetworkXError)
    # source == target
    G2 = nx.DiGraph()
    G2.add_edge("s", "s", cost=3, weight=3)
    G2.add_edge("s", "t", cost=1, weight=1)
    assert pareto_frontier(G2, "s", "s") == [(0, 0)], pareto_frontier(G2, "s", "s")
    # 纯函数
    snap = sorted(G2.edges(data=True))
    pareto_paths(G2, "s", "t")
    assert sorted(G2.edges(data=True)) == snap, "G 被修改"

    print(f"\n{'OK 全部通过' if bad == 0 else f'{bad} 例失败'}"
          f"（A 组有效 {tested} 例；B/C/D/E/F 组各若干）")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
