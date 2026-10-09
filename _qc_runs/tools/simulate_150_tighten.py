# -*- coding: utf-8 -*-
"""精确模拟 150 的 reward 计分：分子 = Σ正向 weight*value + Σnegate -weight*(1-value)，分母 = Σ正向 weight。

用实际 reward-details.json 的 weight/value/negate 验算公式，并测试收紧场景。
"""
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
RUBRICS = W / "FIN3-WKN-150" / "tests" / "rubrics.toml"
REWARDS = {
    e: json.loads((W / "FIN3-WKN-150" / "_rejudge" / e / "verifier" / "reward-details.json").read_text(encoding="utf-8"))
    for e in ["qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
}


def parse_rubrics():
    txt = RUBRICS.read_text(encoding="utf-8")
    blocks = re.split(r"\[\[criterion\]\]", txt)[1:]
    out = {}
    for b in blocks:
        mid = re.search(r'^\s*id\s*=\s*"([^"]+)"', b, re.M)
        mw = re.search(r'^\s*weight\s*=\s*([\d.]+)', b, re.M)
        mn = re.search(r'^\s*negate\s*=\s*(true|false)', b, re.M)
        if mid and mw:
            out[mid.group(1)] = {"weight": float(mw.group(1)),
                                 "negate": mn.group(1) == "true" if mn else False}
    return out


def compute(reward_details, rub_meta, overrides=None):
    """overrides: {id: value} 覆盖某些判据的 value"""
    num = 0.0
    den = 0.0
    for item in reward_details["reward"]["criteria"]:
        cid = item["id"]
        w = rub_meta.get(cid, {}).get("weight", item.get("weight", 0))
        neg = rub_meta.get(cid, {}).get("negate", False)
        v = (overrides or {}).get(cid, item["value"])
        if neg:
            num -= w * (1.0 - v)
        else:
            num += w * v
            den += w
    return max(0.0, min(1.0, num / den)), num, den


def main():
    rub = parse_rubrics()
    print(f"rubrics 判据数 = {len(rub)}, 正向 weight 和 = {sum(r['weight'] for r in rub.values() if not r['negate'])}, negate weight 和 = {sum(r['weight'] for r in rub.values() if r['negate'])}")
    print()

    # 验算
    print("=" * 90)
    print("验算（用 reward-details 实际 value + rubrics 权重/negate）")
    print("=" * 90)
    cur = {}
    for e, rd in REWARDS.items():
        r, n, d = compute(rd, rub)
        cur[e] = r
        actual = json.loads((W / "FIN3-WKN-150" / "_rejudge" / e / "verifier" / "reward.json").read_text(encoding="utf-8"))
        print(f"  {e:<20} 算得 {r:.6f}  实际 {actual['reward']:.6f}  误差 {abs(r-actual['reward']):.8f}")
    mean = sum(cur.values()) / 3
    print(f"  三模型均分 = {mean:.6f}")

    # 列出全1判据（三模型 value >= 0.999）
    all_ids = sorted(rub.keys(), key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 0))
    full = []
    for cid in all_ids:
        vs = [REWARDS[e]["reward"]["criteria"][[c["id"] for c in REWARDS[e]["reward"]["criteria"]].index(cid)]["value"]
              if cid in [c["id"] for c in REWARDS[e]["reward"]["criteria"]] else 0
              for e in REWARDS]
        if all(v >= 0.999 for v in vs) and not rub[cid]["negate"]:
            full.append(cid)
    print(f"\n正向且三模型全1的判据: {len(full)} 条, 权重和 {sum(rub[c]['weight'] for c in full):.0f}")

    # 模拟收紧场景
    def sim(label, overrides_fn, model_tighten):
        """overrides_fn(cid) -> dict {model: value} 或 None"""
        new = {}
        for e, rd in REWARDS.items():
            ov = {}
            for cid in full:
                tgt = model_tighten.get(cid, {})
                if e in tgt:
                    ov[cid] = tgt[e]
            r, n, d = compute(rd, rub, ov)
            new[e] = r
        m = sum(new.values()) / 3
        print(f"\n[{label}]")
        for e in REWARDS:
            print(f"  {e:<20} {cur[e]:.6f} -> {new[e]:.6f} ({new[e]-cur[e]:+.6f})")
        print(f"  三模型均分          {mean:.6f} -> {m:.6f} ({m-mean:+.6f})  {'< 0.7 PASS' if m < 0.7 else '>= 0.7 FAIL'}")

    # 场景1：全1判据三模型都压到 0.7
    sim("场景1: 全1判据三模型都 -> 0.7",
        None,
        {cid: {e: 0.7 for e in REWARDS} for cid in full})

    # 场景2：全1判据三模型都压到 0.5
    sim("场景2: 全1判据三模型都 -> 0.5",
        None,
        {cid: {e: 0.5 for e in REWARDS} for cid in full})

    # 场景3：只压权重>=7的全1判据 -> 0.5
    big = [c for c in full if rub[c]["weight"] >= 7]
    print(f"\n[权重>=7的全1判据: {len(big)} 条, 权重和 {sum(rub[c]['weight'] for c in big):.0f}]")
    sim("场景3: 权重>=7全1判据 -> 0.5",
        None,
        {cid: {e: 0.5 for e in REWARDS} for cid in big})

    # 场景4：只压权重>=7的全1判据 -> 0.7
    sim("场景4: 权重>=7全1判据 -> 0.7",
        None,
        {cid: {e: 0.7 for e in REWARDS} for cid in big})

    # 场景5：高权重全1判据（>=10）-> 0.5
    huge = [c for c in full if rub[c]["weight"] >= 10]
    print(f"\n[权重>=10的全1判据: {len(huge)} 条: {huge}]")
    sim("场景5: 权重>=10全1判据 -> 0.5",
        None,
        {cid: {e: 0.5 for e in REWARDS} for cid in huge})


if __name__ == "__main__":
    main()
