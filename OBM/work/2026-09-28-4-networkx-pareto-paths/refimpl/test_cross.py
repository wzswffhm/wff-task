"""用暴力枚举 oracle 对拍参考实现 pareto_paths。

运行：PYTHONPATH=<networkx 源码目录>:<本目录> python3 test_cross.py
"""
from __future__ import annotations

import random
import sys

import networkx as nx

from pareto_paths import pareto_paths


def dominates(c1, w1, c2, w2):
    return c1 <= c2 and w1 <= w2 and (c1 < c2 or w1 < w2)


def _edges(G, u):
    if G.is_multigraph():
        for _, v, _, d in G.edges(u, keys=True, data=True):
            yield v, d
    else:
        for _, v, d in G.edges(u, data=True):
            yield v, d


def oracle(G, s, t, weight="weight", cost="cost", max_cost=None, max_weight=None):
    pairs = set()

    def dfs(u, visited, c, w):
        if u == t:
            if (max_cost is None or c <= max_cost) and (max_weight is None or w <= max_weight):
                pairs.add((c, w))
            return
        for v, d in _edges(G, u):
            if v in visited:
                continue
            dc = d.get(cost, 0) or 0
            dw = d.get(weight, 0) or 0
            dfs(v, visited | {v}, c + dc, w + dw)

    dfs(s, {s}, 0, 0)
    return sorted(p for p in pairs if not any(dominates(q[0], q[1], p[0], p[1]) for q in pairs))


def sums(G, path, weight="weight", cost="cost"):
    c = w = 0
    for u, v in zip(path, path[1:]):
        d = G.adj[u][v]
        if G.is_multigraph():
            d = min(d.values(), key=lambda x: (x.get(cost, 0) or 0, x.get(weight, 0) or 0))
        c += d.get(cost, 0) or 0
        w += d.get(weight, 0) or 0
    return c, w


def random_case(rng, directed):
    n = rng.randint(3, 7)
    G = nx.DiGraph() if directed else nx.Graph()
    G.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if directed or u < v:
                if rng.random() < 0.45:
                    G.add_edge(u, v, cost=rng.choice([0, 1, 2, 3, 4, 5]), weight=rng.choice([0, 1, 2, 3, 4, 5]))
    return G


def main():
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    rng = random.Random(20260928)
    bad = 0
    for i in range(total):
        if i and i % 100 == 0:
            print(f"  ... {i}/{total}（累计失败 {bad}）", flush=True)
        directed = rng.random() < 0.5
        G = random_case(rng, directed)
        nodes = list(G.nodes())
        if len(nodes) < 2:
            continue
        s = rng.choice(nodes)
        t = rng.choice(nodes)
        mc = rng.choice([None, None, 3, 6, 10])
        mw = rng.choice([None, None, 3, 6, 10])

        exp = oracle(G, s, t, max_cost=mc, max_weight=mw)
        try:
            got = pareto_paths(G, s, t, max_cost=mc, max_weight=mw)
        except nx.NetworkXNoPath:
            if exp:
                print(f"[FAIL {i}] 抛 NoPath 但 oracle 有 {exp}")
                bad += 1
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL {i}] 异常 {type(exc).__name__}: {exc}")
            bad += 1
            continue

        gpairs = [(r["cost"], r["weight"]) for r in got]
        if gpairs != exp:
            print(f"[FAIL {i}] frontier 不一致\n  exp={exp}\n  got={gpairs}\n  s={s} t={t} mc={mc} mw={mw}\n  edges={list(G.edges(data=True))}")
            bad += 1
            continue
        for r in got:
            p = r["path"]
            if len(set(p)) != len(p):
                print(f"[FAIL {i}] 见证非简单路径 {p}")
                bad += 1
                break
            if not p or p[0] != s or p[-1] != t:
                print(f"[FAIL {i}] 见证端点错 {p}")
                bad += 1
                break
            c, w = sums(G, p)
            if (c, w) != (r["cost"], r["weight"]):
                print(f"[FAIL {i}] 见证属性不符 {p} -> {(c,w)} != {(r['cost'], r['weight'])}")
                bad += 1
                break
        # 确定性
        again = pareto_paths(G, s, t, max_cost=mc, max_weight=mw)
        if again != got:
            print(f"[FAIL {i}] 非确定性")
            bad += 1

    print(f"\n{'OK 全部通过' if bad == 0 else f'{bad} 例失败'}（共 {total} 例随机对拍）", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
