# -*- coding: utf-8 -*-
"""汇总 FIN3-WKN-150 三模型逐条判据得分，找出可收紧的判据（三模型全 1 或高分的）。

只读。
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
BASE = W / "FIN3-WKN-150" / "_rejudge"
EXECUTORS = ["qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]

# rubrics 里权重
RUBRICS = W / "FIN3-WKN-150" / "tests" / "rubrics.toml"


def load_rewards():
    data = {}
    for e in EXECUTORS:
        p = BASE / e / "verifier" / "reward-details.json"
        if not p.is_file():
            print(f"  !! 缺 {p}")
            continue
        j = json.loads(p.read_text(encoding="utf-8"))
        crit = j["reward"]["criteria"]
        data[e] = {c["id"]: c for c in crit}
    return data


def load_weights():
    import re
    txt = RUBRICS.read_text(encoding="utf-8")
    # 粗略匹配 [[criterion]] 块里的 id 和 weight
    blocks = re.split(r"\[\[criterion\]\]", txt)[1:]
    weights = {}
    for b in blocks:
        mid = re.search(r'^\s*id\s*=\s*"([^"]+)"', b, re.M)
        mw = re.search(r'^\s*weight\s*=\s*([\d.]+)', b, re.M)
        if mid and mw:
            weights[mid.group(1)] = float(mw.group(1))
    return weights


def main():
    data = load_rewards()
    weights = load_weights()
    print(f"  rubrics 权重条数: {len(weights)}")
    for e in EXECUTORS:
        print(f"  {e}: 判据数={len(data.get(e,{}))}")
    print()

    # 汇总
    all_ids = sorted(set().union(*[set(v.keys()) for v in data.values()]),
                     key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 0))

    print("=" * 110)
    print("逐条判据得分（三模型对比）  ★ = 三模型全 1.0（可收紧候选）")
    print("=" * 110)
    header = f"{'ID':<5} {'权重':<5} {'qwen':<7} {'opus':<7} {'gpt':<7}  {'和':<5} {'标记'}"
    print(header)
    print("-" * 110)

    all_full = []
    high_sum = []  # 三模型和 >= 2.7
    for cid in all_ids:
        w = weights.get(cid, 0)
        scores = []
        row = []
        for e in EXECUTORS:
            c = data.get(e, {}).get(cid)
            v = c["value"] if c else 0.0
            scores.append(v)
            row.append(f"{v:.2f}")
        s = sum(scores)
        flag = ""
        if all(v >= 0.999 for v in scores):
            flag = "★ 全1"
            all_full.append((cid, w, scores))
        elif s >= 2.7:
            flag = "高"
            high_sum.append((cid, w, scores))
        print(f"{cid:<5} {w:<5.0f} {row[0]:<7} {row[1]:<7} {row[2]:<7}  {s:<5.2f} {flag}")

    print()
    print("=" * 110)
    print(f"三模型全 1.0 的判据：{len(all_full)} 条")
    print("=" * 110)
    total_w = sum(w for _, w, _ in all_full)
    all_w = sum(weights.values())
    print(f"  权重和 {total_w:.0f} / {all_w:.0f}  ({100*total_w/all_w:.1f}%)")
    for cid, w, sc in all_full:
        print(f"    {cid:<5} 权重 {w:<5.0f} {sc}")

    print()
    print("=" * 110)
    print(f"三模型和 >= 2.7 但非全 1：{len(high_sum)} 条")
    print("=" * 110)
    for cid, w, sc in high_sum:
        print(f"    {cid:<5} 权重 {w:<5.0f} {sc}  和={sum(sc):.2f}")

    # 计算：如果把全 1 判据压到 0.7（三模型都），新的三模型均分
    print()
    print("=" * 110)
    print("情景模拟：若把全 1 判据三模型都压到 0.7")
    print("=" * 110)
    import copy
    for e in EXECUTORS:
        cur = sum(data[e][cid]["value"] for cid in all_ids if cid in data[e])
        maxs = sum(weights.get(cid, 0) for cid in all_ids)
        print(f"  {e}: 当前分子={cur:.4f} 分母={maxs:.0f} reward={cur/maxs:.6f}")

    # 三模型均分当前
    rewards = {e: sum(data[e][cid]["value"] for cid in all_ids if cid in data[e]) /
                    sum(weights.get(cid, 0) for cid in all_ids) for e in EXECUTORS}
    print()
    print(f"  三模型均分当前 = {sum(rewards.values())/3:.6f}")

    # 模拟：全1判据 value->0.7
    for e in EXECUTORS:
        new = 0.0
        maxs = sum(weights.get(cid, 0) for cid in all_ids)
        for cid in all_ids:
            v = data[e][cid]["value"]
            if any(cid == f for f, _, _ in all_full):
                v = 0.7
            new += v
        rewards[e] = new / maxs
    print(f"  模拟后三模型均分 = {sum(rewards.values())/3:.6f}  ({'< 0.7' if sum(rewards.values())/3 < 0.7 else '>= 0.7'})")

    # 打印压到 0.7 时每条全1判据的 reasoning（供人判断收紧方向）
    print()
    print("=" * 110)
    print("全 1 判据的 reasoning（qwen 视角，判断可否收紧）")
    print("=" * 110)
    for cid, w, sc in all_full:
        c = data["qwen3.8-max-0902"].get(cid)
        if not c:
            continue
        desc = c.get("description", "")
        rsn = c.get("reasoning", "")
        # 提取中文描述的前 120 字
        print(f"\n  [{cid}] 权重 {w:.0f}")
        print(f"    描述: {desc[:160]}...")
        print(f"    理由: {rsn[:200]}...")


if __name__ == "__main__":
    main()
