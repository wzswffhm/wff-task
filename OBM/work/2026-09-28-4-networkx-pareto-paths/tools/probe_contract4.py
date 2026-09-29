"""契约探针（F2P 未覆盖面）— 2026-09-28-4 networkx pareto_paths

对同一条契约，比较「Agent 实现」与「参考实现」在 **F2P 未覆盖**的行为上是否分歧。
用同一份脚本跑两遍（MODE=agent / MODE=ref），再 diff 输出。

用法（Windows 托管 python）：
  MODE=agent PYTHONPATH=<app-context>                    python probe_contract4.py
  MODE=ref   PYTHONPATH=<baseline-app>;<refimpl-dir>     python probe_contract4.py
"""
import os
import random
import sys
from itertools import permutations

import networkx as nx

MODE = os.environ.get("MODE", "agent")

if MODE == "ref":
    from pareto_paths import pareto_paths as _pp
    nx.pareto_paths = _pp


def norm(result):
    """把返回值归一化成可比较的字符串（不依赖顺序之外的细节）。"""
    if result is None:
        return "None"
    out = []
    for r in result:
        p = list(r["path"])
        out.append((r["cost"], r["weight"], tuple(p)))
    out.sort(key=lambda x: (x[0], x[1], x[2]))
    return ";".join(f"({c},{w},{list(p)})" for c, w, p in out)


def try_case(label, fn):
    try:
        v = fn()
        print(f"{label}: OK {v if isinstance(v, str) else norm(v)}")
    except Exception as e:
        print(f"{label}: RAISE {type(e).__name__}")


def brute(G, s, t, wn, cn):
    """暴力枚举所有简单路径，返回非支配 (cost,weight) → 见证集合。"""
    pairs = {}
    nodes = list(G.nodes)
    mids = [n for n in nodes if n not in (s, t)]
    for r in range(0, len(mids) + 1):
        for combo in permutations(mids, r):
            seq = [s, *combo, t]
            ok = all(G.has_edge(seq[i], seq[i + 1]) for i in range(len(seq) - 1))
            if not ok:
                continue
            c = sum(G[seq[i]][seq[i + 1]].get(cn, 0) for i in range(len(seq) - 1))
            w = sum(G[seq[i]][seq[i + 1]].get(wn, 0) for i in range(len(seq) - 1))
            pairs.setdefault((c, w), []).append(tuple(seq))
    feasible = set(pairs)
    front = {p for p in feasible
             if not any((q[0] <= p[0] and q[1] <= p[1] and q != p) for q in feasible)}
    return front, pairs


print(f"########## MODE={MODE}  networkx={nx.__version__} ##########")

# 1) 双上界同时收窄
G = nx.DiGraph()
G.add_edge("s", "a", cost=1, weight=5); G.add_edge("a", "t", cost=1, weight=5)
G.add_edge("s", "b", cost=3, weight=1); G.add_edge("b", "t", cost=1, weight=1)
G.add_edge("s", "t", cost=4, weight=3)
try_case("01_both_bounds", lambda: nx.pareto_paths(G, "s", "t", max_cost=4, max_weight=9))
try_case("02_bounds_exclude_all", lambda: nx.pareto_paths(G, "s", "t", max_cost=0, max_weight=0))

# 2) 非字符串节点
G2 = nx.DiGraph()
G2.add_edge(1, (2, 3), cost=1, weight=1); G2.add_edge((2, 3), 4, cost=1, weight=2)
try_case("03_tuple_nodes", lambda: nx.pareto_paths(G2, 1, 4))

# 3) 自环（正代价）
G3 = nx.DiGraph()
G3.add_edge("s", "s", cost=1, weight=1); G3.add_edge("s", "t", cost=2, weight=2)
try_case("04_selfloop_positive", lambda: nx.pareto_paths(G3, "s", "t"))
try_case("05_selfloop_same_node", lambda: nx.pareto_paths(G3, "s", "s"))

# 4) 缺省属性当 0
G4 = nx.DiGraph()
G4.add_edge("s", "a", cost=1)                 # 无 weight
G4.add_edge("a", "t", weight=2)               # 无 cost
try_case("06_missing_attrs_zero", lambda: nx.pareto_paths(G4, "s", "t"))

# 5) 无向图
G5 = nx.Graph()
G5.add_edge("s", "a", cost=1, weight=3); G5.add_edge("a", "t", cost=1, weight=3)
G5.add_edge("s", "t", cost=3, weight=1)
try_case("07_undirected", lambda: nx.pareto_paths(G5, "s", "t"))

# 6) target 存在但不可达
G6 = nx.DiGraph()
G6.add_edge("s", "a", cost=1, weight=1); G6.add_node("z")
try_case("08_unreachable", lambda: nx.pareto_paths(G6, "s", "z"))

# 7) 负值出现在「不参与任何 s-t 路径」的边上
G7 = nx.DiGraph()
G7.add_edge("s", "t", cost=1, weight=1)
G7.add_edge("x", "y", cost=-5, weight=1)      # 与目标无关
try_case("09_negative_offpath", lambda: nx.pareto_paths(G7, "s", "t"))

# 8) 自定义属性名
G8 = nx.DiGraph()
G8.add_edge("s", "a", w=2, c=1); G8.add_edge("a", "t", w=1, c=2)
try_case("10_custom_attr_names", lambda: nx.pareto_paths(G8, "s", "t", weight="w", cost="c"))

# 9) 多重图
G9 = nx.MultiDiGraph()
G9.add_edge("s", "t", cost=1, weight=1)
try_case("11_multigraph", lambda: nx.pareto_paths(G9, "s", "t"))

# 10) 确定性 + 纯函数
G10 = nx.DiGraph()
G10.add_edge("s", "a", cost=0, weight=0); G10.add_edge("a", "s", cost=0, weight=0)
G10.add_edge("s", "t", cost=1, weight=1)
r1 = norm(nx.pareto_paths(G10, "s", "t")); r2 = norm(nx.pareto_paths(G10, "s", "t"))
print(f"12_deterministic: {'SAME' if r1 == r2 else 'DIFF'} {r1}")
before = sorted(G10.edges(data=True)); nx.pareto_paths(G10, "s", "t")
print(f"13_graph_unmodified: {'YES' if sorted(G10.edges(data=True)) == before else 'NO'}")

# 11) 零权零代价环（不得死循环、见证必须简单）
G11 = nx.DiGraph()
G11.add_edge("s", "a", cost=0, weight=0); G11.add_edge("a", "b", cost=0, weight=0)
G11.add_edge("b", "a", cost=0, weight=0); G11.add_edge("b", "t", cost=0, weight=0)
try_case("14_zero_cycle", lambda: nx.pareto_paths(G11, "s", "t"))

# 12) 平局：多条不同简单路径给出同一 (cost,weight)
G12 = nx.DiGraph()
G12.add_edge("s", "a", cost=1, weight=1); G12.add_edge("a", "t", cost=1, weight=1)
G12.add_edge("s", "b", cost=1, weight=1); G12.add_edge("b", "t", cost=1, weight=1)
try_case("15_tie_two_witnesses", lambda: nx.pareto_paths(G12, "s", "t"))


def check_tie():
    res = nx.pareto_paths(G12, "s", "t")
    paths = {tuple(r["path"]) for r in res}
    assert paths <= {("s", "a", "t"), ("s", "b", "t")}, paths
    return f"witnesses={sorted(paths)}"


try_case("16_tie_witness_valid", check_tie)

# 13) 无向 + 平行反向边
G13 = nx.DiGraph()
G13.add_edge("s", "t", cost=2, weight=2)
G13.add_edge("t", "s", cost=1, weight=1)
try_case("17_antiparallel", lambda: nx.pareto_paths(G13, "s", "t"))

# 14) 源点不在图中
try_case("18_missing_source", lambda: nx.pareto_paths(G13, "nope", "t"))
# 15) 目标是源点且不在图中
try_case("19_missing_self", lambda: nx.pareto_paths(G13, "nope", "nope"))

# 16) 比 F2P 更大更强的随机对拍（更密、更多零、更多平局）
rng = random.Random(424242)
mismatch = 0
for i in range(400):
    n = rng.randint(5, 8)
    p = rng.choice([0.35, 0.5, 0.65])
    G = nx.DiGraph()
    G.add_nodes_from(range(n))
    for u in range(n):
        for v in range(n):
            if u != v and rng.random() < p:
                G.add_edge(u, v, cost=rng.choice([0, 0, 1, 1, 2, 3]), weight=rng.choice([0, 0, 1, 1, 2, 3]))
    if 0 not in G or n - 1 not in G:
        continue
    front, pairs = brute(G, 0, n - 1, "weight", "cost")
    if not pairs:
        continue
    try:
        res = nx.pareto_paths(G, 0, n - 1)
    except Exception as e:
        mismatch += 1
        if mismatch <= 3:
            print(f"   [{i}] RAISE {type(e).__name__}")
        continue
    got = {(r["cost"], r["weight"]) for r in res}
    if got != front:
        mismatch += 1
        if mismatch <= 3:
            print(f"   [{i}] FRONTIER DIFF got={sorted(got)} exp={sorted(front)}")
        continue
    for r in res:
        pth = list(r["path"])
        assert pth[0] == 0 and pth[-1] == n - 1, pth
        assert len(set(pth)) == len(pth), f"not simple: {pth}"
        c = sum(G[pth[k]][pth[k + 1]].get("cost", 0) for k in range(len(pth) - 1))
        w = sum(G[pth[k]][pth[k + 1]].get("weight", 0) for k in range(len(pth) - 1))
        if (c, w) != (r["cost"], r["weight"]):
            mismatch += 1
            if mismatch <= 3:
                print(f"   [{i}] WITNESS SUM DIFF {pth} {c},{w} vs {r['cost']},{r['weight']}")
            break
print(f"20_random_crosscheck: {'PASS' if mismatch == 0 else f'{mismatch} MISMATCH'} (300 例)")
print("########## END ##########")
