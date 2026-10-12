# -*- coding: utf-8 -*-
"""列出 150 中「正向 + 三模型全1 + 权重>=7」的判据，打印完整描述 + 三模型 reasoning，供判断收紧方向。"""
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
        md = re.search(r'^\s*description\s*=\s*"((?:[^"\\]|\\.)*)"', b, re.M | re.S)
        if mid and mw:
            out[mid.group(1)] = {
                "weight": float(mw.group(1)),
                "negate": (mn.group(1) == "true") if mn else False,
                "desc": md.group(1) if md else "",
            }
    return out


def main():
    rub = parse()
    # 找正向 + 三模型全1 + 权重>=7
    all_ids = sorted(rub.keys(), key=lambda x: (x[0], int(x[1:]) if x[1:].isdigit() else 0))
    target = []
    for cid in all_ids:
        if rub[cid]["negate"]:
            continue
        vals = []
        for e in EXEC:
            crit = {c["id"]: c for c in REWARDS[e]["reward"]["criteria"]}
            vals.append(crit.get(cid, {}).get("value", 0))
        if all(v >= 0.999 for v in vals) and rub[cid]["weight"] >= 7:
            target.append((cid, rub[cid]["weight"]))

    print(f"正向 + 三模型全1 + 权重>=7: {len(target)} 条")
    print(f"  {[(c, w) for c, w in target]}")
    print(f"  权重和 = {sum(w for _, w in target):.0f}")
    print()

    for cid, w in target:
        print("=" * 100)
        print(f"[{cid}]  权重 {w:.0f}")
        print("=" * 100)
        desc = rub[cid]["desc"]
        print(f"  描述（原始）:\n    {desc[:600]}")
        # 三模型 reasoning
        for e in EXEC:
            crit = {c["id"]: c for c in REWARDS[e]["reward"]["criteria"]}
            rsn = crit.get(cid, {}).get("reasoning", "")
            print(f"\n  [{e}] reasoning:\n    {rsn[:450]}")
        print()


if __name__ == "__main__":
    main()
