#!/usr/bin/env python3
"""检查「难度是否被单一口径歧义撑着」。

用法:
    python check_cross_model_concentration.py <task-dir> [<runs-dir>] [--threshold 0.25] [--strict]

  task-dir  : 题目目录（含 tests/rubrics.toml 与 task.toml）
  runs-dir  : 跑分产物目录，默认为 <task-dir>/../跑分产物与轨迹/<题目目录名>
  --strict  : 集中度超阈值时返回 1（默认只提示，返回 0）

背景（v2.4 新增）：某题 51 条判据里有 15 条被三个模型**一致**判 0，权重合计 119/298＝39.9%，
全部挂在「A 项目完全稀释持股比例」这一处口径上——而该口径在材料里自相矛盾
（一处写"按融资前已发行股份计算"、另一处只提"未考虑期权池"），即难度实际由**题面歧义**撑着，
而不是由真实专业难度撑着。这类题目一旦被甲方人检点到，会按"靠题面歧义刷低分"直接打回；
更麻烦的是：把口径锁死之后模型很可能就算对了，三模型均值会被推高、难度档当场失效。

本脚本把这一情形变成可机械发现的信号：列出「三个执行体同时未满分」的判据、其权重合计与占正分池比例。
**它只报警、不判对错**：高集中度也可能是合理设计（例如某条专业判断确实全体答错），
需要人工按 SKILL.md「三道易漏的自查」第 3 条逐条追问「口径能否从材料唯一推出」。
"""
import json
import os
import sys

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

MODELS = ["gpt-5.6-sol", "claude-opus-4-8", "qwen3.8-max-0902"]
DEFAULT_THRESHOLD = 0.25


def load_rubrics(task_dir):
    with open(os.path.join(task_dir, "tests", "rubrics.toml"), "rb") as fh:
        data = tomllib.load(fh)
    weights, negate = {}, set()
    for c in data["criterion"]:
        weights[c["id"]] = float(c["weight"])
        if c.get("negate"):
            negate.add(c["id"])
    pool = sum(w for k, w in weights.items() if k not in negate)
    return weights, negate, pool


def load_values(runs_dir):
    per_model = {}
    for m in MODELS:
        p = os.path.join(runs_dir, m, "reward-details.json")
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as fh:
            det = json.load(fh)["reward"]["criteria"]
        per_model[m] = {c["id"]: float(c["value"]) for c in det}
    return per_model


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    strict = "--strict" in sys.argv
    threshold = DEFAULT_THRESHOLD
    for i, a in enumerate(sys.argv):
        if a == "--threshold" and i + 1 < len(sys.argv):
            threshold = float(sys.argv[i + 1])
    if not args:
        raise SystemExit(__doc__)

    task_dir = os.path.abspath(args[0].rstrip("/\\"))
    runs_dir = args[1] if len(args) > 1 else os.path.join(
        os.path.dirname(task_dir), "跑分产物与轨迹", os.path.basename(task_dir))
    if not os.path.isdir(runs_dir):
        raise SystemExit(f"跑分目录不存在: {runs_dir}")

    weights, negate, pool = load_rubrics(task_dir)
    per_model = load_values(runs_dir)
    if len(per_model) < 2:
        raise SystemExit(f"可用执行体不足（找到 {sorted(per_model)}）")

    zero, partial = [], []
    for cid in weights:
        vals = [per_model[m].get(cid) for m in per_model if cid in per_model[m]]
        if len(vals) < 2:
            continue
        if all(v == 0.0 for v in vals):
            zero.append(cid)
        elif all(v < 1.0 for v in vals):
            partial.append(cid)

    zw = sum(weights[c] for c in zero if c not in negate)
    pw = sum(weights[c] for c in partial if c not in negate)
    share = zw / pool if pool else 0.0

    print(f"题目: {os.path.basename(task_dir)}   执行体: {sorted(per_model)}")
    print(f"正分池: {pool:g}   扣分项: {len(negate)} 条")
    print()
    print(f"[全体一致 0 分] {len(zero)} 条，权重合计 {zw:g}"
          f"（占正分池 {share:.1%}）")
    for cid in sorted(zero, key=lambda c: -weights[c]):
        print(f"    {cid:<6} w={weights[cid]:<5g} {'(negate)' if cid in negate else ''}")
    print()
    print(f"[全体未满分但非 0] {len(partial)} 条，权重合计 {pw:g}"
          f"（占正分池 {pw / pool:.1%}）")
    for cid in sorted(partial, key=lambda c: -weights[c]):
        vals = {m: per_model[m][cid] for m in per_model if cid in per_model[m]}
        print(f"    {cid:<6} w={weights[cid]:<5g} {vals}")
    print()

    if share >= threshold:
        print(f"[WARN] 「全体 0 分」判据的正分占比 {share:.1%} ≥ 阈值 {threshold:.0%}。")
        print("       请按 SKILL.md「三道易漏的自查」第 3 条逐条追问：")
        print("       ① 这些判据的口径/换算能否从 environment/input_files/ 原文**唯一**推出？")
        print("       ② 材料是否存在自相矛盾（一处写 A、另一处写 B）？")
        print("       ③ 若属歧义：锁口径=改材料（需重跑 agent）／放宽判据=改判据（只重跑判官）；")
        print("          并按「该组权重 ÷ 正分池」预估锁口径后的分数变化与难度档风险。")
        return 1 if strict else 0

    print(f"[OK] 集中度 {share:.1%} 低于阈值 {threshold:.0%}，未见「单一口径撑着难度」的信号。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
