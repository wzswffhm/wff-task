# -*- coding: utf-8 -*-
"""补充：三模型共同失分清单 + N类判据raw + reward.json 对比。"""
import json, sys, io, zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")

def load(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def t(s, n):
    return (s or "").replace("\n", " ").strip()[:n]

GROUPS = {
    "149-fix8": {
        "oracle": r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹\oracle",
        "qwen":   r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹\qwen3.8-max-0902",
        "gpt":    r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹\gpt-5.6-sol",
        "opus":   r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹\claude-opus-4-8",
    },
    "150-fix6": {
        "oracle": r"work_fin-b01_20261006_fix6-150\FIN3-WKN-150\跑分产物与轨迹\oracle",
        "qwen":   r"work_fin-b01_20261006_fix6-150\FIN3-WKN-150\跑分产物与轨迹\qwen3.8-max-0902",
        "gpt":    r"work_fin-b01_20261006_fix6-150\FIN3-WKN-150\跑分产物与轨迹\gpt-5.6-sol",
        "opus":   r"work_fin-b01_20261006_fix6-150\FIN3-WKN-150\跑分产物与轨迹\claude-opus-4-8",
    },
    "FIN-PE-001": {
        "oracle": r"_reference\zq-金融-私募股权-20260930\跑分产物与轨迹\FIN-PE-001\oracle",
        "qwen":   r"_reference\zq-金融-私募股权-20260930\跑分产物与轨迹\FIN-PE-001\qwen3.8-max-0902",
        "gpt":    r"_reference\zq-金融-私募股权-20260930\跑分产物与轨迹\FIN-PE-001\gpt-5.6-sol",
        "opus":   r"_reference\zq-金融-私募股权-20260930\跑分产物与轨迹\FIN-PE-001\claude-opus-4-8",
    },
}

print("=" * 90)
print("A. reward.json 对比（reward / criteria_counted / verifier_error）与 details score")
print("=" * 90)
for g, mp in GROUPS.items():
    print(f"\n[{g}]")
    for m, d in mp.items():
        try:
            rj = load(ROOT / d / "reward.json")
            rd = load(ROOT / d / "reward-details.json")
            score = rd.get("reward", {}).get("score")
            print(f"  {m:<10} reward.json={json.dumps(rj, ensure_ascii=False)}  details.score={score}")
        except Exception as e:
            print(f"  {m}: 读取失败 {e}")

print("\n\n" + "=" * 90)
print("B. 三模型(qwen/gpt/opus)全部 <1 而 oracle=1 的判据（真正难题，可压低均分）")
print("=" * 90)
for g, mp in GROUPS.items():
    data = {}
    for m, d in mp.items():
        rd = load(ROOT / d / "reward-details.json")
        r = rd.get("reward", rd)
        data[m] = {c["id"]: c for c in r.get("criteria", [])}
    print(f"\n[{g}]")
    for cid, qc in data["qwen"].items():
        vals = {m: data[m].get(cid, {}).get("value") for m in ("oracle", "qwen", "gpt", "opus")}
        if vals["oracle"] == 1.0 and all(vals[m] is not None and vals[m] < 1 for m in ("qwen", "gpt", "opus")):
            print(f"  {cid} (w={qc.get('weight')}) {vals}")
            print(f"    desc: {t(qc.get('description'),150)}")
            print(f"    qwen失分reasoning: {t(qc.get('reasoning'),300)}")

print("\n\n" + "=" * 90)
print("C. N类（负向判据）各模型 raw/value 明细")
print("=" * 90)
for g, mp in GROUPS.items():
    data = {}
    for m, d in mp.items():
        rd = load(ROOT / d / "reward-details.json")
        r = rd.get("reward", rd)
        data[m] = {c["id"]: c for c in r.get("criteria", [])}
    print(f"\n[{g}]")
    for cid, qc in data["qwen"].items():
        if not cid.startswith("N"):
            continue
        row = []
        for m in ("oracle", "qwen", "gpt", "opus"):
            c = data[m].get(cid, {})
            row.append(f"{m}: value={c.get('value')}, raw={c.get('raw')!r}")
        print(f"  {cid}: " + " | ".join(row))
        print(f"    desc(前120): {t(qc.get('description'),120)}")
        for m in ("qwen", "gpt", "opus"):
            c = data[m].get(cid, {})
            if c.get("value", 1) < 1:
                print(f"    {m} reasoning(失分,前300): {t(c.get('reasoning'),300)}")

# 151 补充：三模型全失分
print("\n\n" + "=" * 90)
print("D. FIN3-WKN-151（来自 zip）三模型全失分判据")
print("=" * 90)
ZP = ROOT / "work_fin-b01_20261006-151.zip"
with zipfile.ZipFile(ZP) as z:
    data = {}
    for m in ["oracle", "qwen3.8-max-0902", "gpt-5.6-sol", "claude-opus-4-8"]:
        d = json.loads(z.read(f"work_fin-b01_20261006-151/跑分产物与轨迹/{m}/reward-details.json").decode("utf-8"))
        r = d.get("reward", d)
        data[m] = {c["id"]: c for c in r.get("criteria", [])}
    q = data["qwen3.8-max-0902"]
    for cid, qc in q.items():
        vals = {m: data[m].get(cid, {}).get("value") for m in data}
        if vals["oracle"] == 1.0 and all(vals[m] is not None and vals[m] < 1 for m in ("qwen3.8-max-0902", "gpt-5.6-sol", "claude-opus-4-8")):
            print(f"  {cid} (w={qc.get('weight')}) {vals}")
            print(f"    desc: {t(qc.get('description'),150)}")
            print(f"    qwen失分reasoning: {t(qc.get('reasoning'),300)}")
