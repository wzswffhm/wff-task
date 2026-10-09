# -*- coding: utf-8 -*-
"""测算温和收紧方案：只改 R29/R30（likert 5分制，提高锚点）+ 可选 R08（binary 收紧）。

模拟不同 anchor 强度下，判官给 value 的档位（满分为 1.0 = 5 分，逐档下降）。
找出能压到 0.70 以下的最小改动集。
"""
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
RUBRICS = W / "FIN3-WKN-150" / "tests" / "rubrics.toml"
EXEC = ["qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
REWARDS = {e: json.loads((W / "FIN3-WKN-150" / "_rejudge" / e / "verifier" / "reward-details.json").read_text(encoding="utf-8")) for e in EXEC}


def parse():
    txt = RUBRICS.read_text(encoding="utf-8")
    blocks = re.split(r"\[\[criterion\]\]", txt)[1:]
    out = {}
    for b in blocks:
        mid = re.search(r'^\s*id\s*=\s*"([^"]+)"', b, re.M)
        mw = re.search(r'^\s*weight\s*=\s*([\d.]+)', b, re.M)
        mn = re.search(r'^\s*negate\s*=\s*(true|false)', b, re.M)
        mt = re.search(r'^\s*type\s*=\s*"([^"]+)"', b, re.M)
        if mid and mw:
            out[mid.group(1)] = {
                "weight": float(mw.group(1)),
                "negate": (mn.group(1) == "true") if mn else False,
                "type": mt.group(1) if mt else "",
            }
    return out


def compute(rub, overrides):
    """overrides: {cid: {model: value}}"""
    scores = {}
    for e in EXEC:
        num, den = 0.0, 0.0
        crit = {c["id"]: c for c in REWARDS[e]["reward"]["criteria"]}
        for cid, meta in rub.items():
            w, neg = meta["weight"], meta["negate"]
            v = overrides.get(cid, {}).get(e)
            if v is None:
                v = crit.get(cid, {}).get("value", 0.0)
            if neg:
                num -= w * (1.0 - v)
            else:
                num += w * v
                den += w
        scores[e] = max(0.0, min(1.0, num / den))
    return scores


def main():
    rub = parse()
    base = compute(rub, {})
    base_mean = sum(base.values()) / 3
    print(f"当前: " + "  ".join(f"{e}={base[e]:.4f}" for e in EXEC))
    print(f"      三模型均分 = {base_mean:.6f}  ({'PASS' if base_mean < 0.7 else 'FAIL'})")

    likert_ids = [c for c, m in rub.items() if m["type"] == "likert"]
    print(f"\nlikert 判据: {likert_ids}")
    # 全1的 likert
    full_likert = []
    for cid in likert_ids:
        vals = []
        for e in EXEC:
            crit = {c["id"]: c for c in REWARDS[e]["reward"]["criteria"]}
            vals.append(crit.get(cid, {}).get("value", 0))
        if all(v >= 0.999 for v in vals):
            full_likert.append(cid)
    print(f"  全1 的 likert: {full_likert}")

    print("\n" + "=" * 80)
    print("温和收紧方案测算（likert 判据压档）")
    print("=" * 80)

    # 场景：只改全1的 likert（R29/R30/R34/R08...）逐档下压
    # likert points=5，value 档位：5分=1.0, 4分=0.8, 3分=0.6, 2分=0.4, 1分=0.2
    scenarios = [
        ("全1 likert -> 0.8 (5分降4分)", {cid: {e: 0.8 for e in EXEC} for cid in full_likert}),
        ("全1 likert -> 0.6 (5分降3分)", {cid: {e: 0.6 for e in EXEC} for cid in full_likert}),
        ("全1 likert -> 0.4 (5分降2分)", {cid: {e: 0.4 for e in EXEC} for cid in full_likert}),
    ]

    # 只选 R29/R30（权重 7 各，最典型定性判据）
    r29_r30 = [c for c in ("R29", "R30") if c in full_likert]
    print(f"\n-- 只改 R29+R30 (权重 {sum(rub[c]['weight'] for c in r29_r30):.0f}) --")
    for label, mult in [("-> 0.8", 0.8), ("-> 0.6", 0.6), ("-> 0.4", 0.4)]:
        ov = {cid: {e: mult for e in EXEC} for cid in r29_r30}
        s = compute(rub, ov)
        m = sum(s.values()) / 3
        print(f"  {label}: 均分 {m:.6f}  ({'PASS' if m < 0.7 else 'FAIL'})  " +
              "  ".join(f"{e}={s[e]:.4f}" for e in EXEC))

    print(f"\n-- R29+R30+R08（R08 binary，若判官改严后判0） --")
    for r08v in [1.0, 0.0]:
        ov = {cid: {e: mult for e in EXEC} for cid in r29_r30 for mult in [0.7]}
        ov = {cid: {e: 0.7 for e in EXEC} for cid in r29_r30}
        if r08v == 0.0:
            ov["R08"] = {e: 0.0 for e in EXEC}
        s = compute(rub, ov)
        m = sum(s.values()) / 3
        print(f"  R29/R30->0.7, R08->{r08v}: 均分 {m:.6f}  ({'PASS' if m < 0.7 else 'FAIL'})")

    # 关键：如果只把 R29/R30 从 1.0 压到 0.7，均分降多少？
    print("\n-- 关键测算：R29+R30 各压到不同值 --")
    for tgt in [0.7, 0.6, 0.5, 0.4]:
        ov = {cid: {e: tgt for e in EXEC} for cid in r29_r30}
        s = compute(rub, ov)
        m = sum(s.values()) / 3
        delta = base_mean - m
        print(f"  -> {tgt}: 均分 {m:.6f} (降 {delta:.6f})  {'PASS' if m < 0.7 else 'FAIL'}")

    # 找出最小改动：哪几条全1判据 + 压到多少能刚好 < 0.7
    print("\n-- 单条判据压到 0.5 时的均分降幅（找最有效的单条） --")
    all_full = []
    for cid in rub:
        if rub[cid]["negate"]:
            continue
        vals = []
        for e in EXEC:
            crit = {c["id"]: c for c in REWARDS[e]["reward"]["criteria"]}
            vals.append(crit.get(cid, {}).get("value", 0))
        if all(v >= 0.999 for v in vals):
            all_full.append(cid)
    for cid in sorted(all_full):
        ov = {cid: {e: 0.5 for e in EXEC}}
        s = compute(rub, ov)
        m = sum(s.values()) / 3
        print(f"  {cid} (w={rub[cid]['weight']:.0f}, {rub[cid]['type']}): 均分 {base_mean:.4f} -> {m:.4f} (降 {base_mean-m:.4f})")


if __name__ == "__main__":
    main()
