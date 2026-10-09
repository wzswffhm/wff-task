# -*- coding: utf-8 -*-
"""验证候选「收紧前判据」是否逐条等于判分快照，并自洽。

候选：work_fin-b01_20261006_fix3-150/FIN3-WKN-150/{tests/rubrics.toml, rubrics.json}
基准：跑分产物与轨迹/<ex>/reward-details.json 的 criteria[].description（判分时容器内判据）
"""
import json
import pathlib
import sys
import tomllib

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
CAND = H / "work_fin-b01_20261006_fix3-150" / "FIN3-WKN-150"
ARCH = H / "work-金融-私募股权投资-20261008" / "FIN3-WKN-150" / "跑分产物与轨迹"
EXEC = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]

cand_toml = tomllib.loads((CAND / "tests" / "rubrics.toml").read_text(encoding="utf-8"))["criterion"]
cand_json = json.loads((CAND / "rubrics.json").read_text(encoding="utf-8"))["items"]
cand_t = {c["id"]: c["description"] for c in cand_toml}
cand_j = {i["id"]: i for i in cand_json}

print("=" * 100)
print("1) 候选 toml 的 36 条 description 与四场判分快照逐条比对")
print("=" * 100)
print(f"  候选 toml 判据数: {len(cand_toml)}")
allok = True
for ex in EXEC:
    d = json.loads((ARCH / ex / "reward-details.json").read_text(encoding="utf-8"))["reward"]
    snap = {c["id"]: c["description"] for c in d["criteria"]}
    diff = [k for k in snap if snap.get(k) != cand_t.get(k)]
    n_snap = len(snap)
    ok = not diff and n_snap == 36
    allok &= ok
    print(f"  [{'OK' if ok else '!!'}] {ex:<18} 快照 {n_snap} 条  不等条目={diff if diff else '无'}")
    # 顺带核对权重
    wdiff = [c["id"] for c in d["criteria"]
             if c["id"] in {x["id"] for x in cand_toml}
             and float(c.get("weight") or 0) != float(
                 next(x["weight"] for x in cand_toml if x["id"] == c["id"]))]
    if wdiff:
        print(f"        权重不一致: {wdiff}")
        allok = False

print()
print("=" * 100)
print("2) 候选 toml 与候选 json 自洽（description 一致 + levels 齐备）")
print("=" * 100)
dj = [k for k in cand_t if cand_t[k] != cand_j.get(k, {}).get("description")]
print(f"  toml vs json description 不等条目: {dj if dj else '无'}")
lev_bad = []
for i in cand_json:
    lv = i.get("levels")
    if i.get("kind") == "gradient" or lv:
        if not isinstance(lv, dict) or len(lv) != 5:
            lev_bad.append((i["id"], type(lv).__name__, (len(lv) if isinstance(lv, dict) else None)))
print(f"  levels 结构异常条目: {lev_bad if lev_bad else '无'}")
allok &= (not dj and not lev_bad)

print()
print("=" * 100)
print("3) R29 / R30 / R31 关键文本")
print("=" * 100)
for k in ("R29", "R30", "R31"):
    d = cand_t[k]
    print(f"  {k}: 含'量化拆解'={'量化拆解' in d}  含'个别'={'个别' in d}  长度={len(d)}")
    print(f"      {d[:150]}...")
print()
print("=" * 100)
print("4) 候选 json 的 R29/R30 levels（回退后这些就是最终 levels）")
print("=" * 100)
for k in ("R29", "R30"):
    lv = cand_j[k].get("levels") or {}
    print(f"  {k}:")
    for kk in ("1", "0.75", "0.5", "0.25", "0"):
        print(f"      {kk:>4} -> {str(lv.get(kk))[:96]}")

print()
print("=" * 100)
print(f">>> {'候选判据完全等于判分快照，可以回退' if allok else '候选判据与判分快照不一致，回退会破坏 #2，勿执行'}")
print("=" * 100)
sys.exit(0 if allok else 1)
