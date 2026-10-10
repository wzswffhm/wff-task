# -*- coding: utf-8 -*-
"""从 work_fin-b01_20261006-151.zip 读取四模型 reward-details 并逐判据对比。"""
import json, sys, io, zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ZP = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\work_fin-b01_20261006-151.zip")

MODELS = ["oracle", "qwen3.8-max-0902", "gpt-5.6-sol", "claude-opus-4-8"]

def t(s, n):
    return (s or "").replace("\n", " ").strip()[:n]

with zipfile.ZipFile(ZP) as z:
    names = z.namelist()
    # summary
    sums = [n for n in names if n.endswith("summary.json")]
    for s in sums:
        d = json.loads(z.read(s).decode("utf-8"))
        print(f"[summary: {s}]\n{json.dumps(d, ensure_ascii=False, indent=1)[:2500]}\n")
    data = {}
    scores = {}
    for m in MODELS:
        p = f"work_fin-b01_20261006-151/跑分产物与轨迹/{m}/reward-details.json"
        if p not in names:
            print(f"缺少 {p}")
            continue
        d = json.loads(z.read(p).decode("utf-8"))
        r = d.get("reward", d)
        data[m] = {c["id"]: c for c in r.get("criteria", [])}
        scores[m] = r.get("score")
    # reward.json 概览
    print("=== reward.json (reward/criteria_counted/verifier_error) ===")
    for m in MODELS:
        p = f"work_fin-b01_20261006-151/跑分产物与轨迹/{m}/reward.json"
        if p in names:
            print(m, json.dumps(json.loads(z.read(p).decode("utf-8")), ensure_ascii=False))

print("\n总分:", scores)
if "qwen3.8-max-0902" in data:
    q = data["qwen3.8-max-0902"]
    cols = [m for m in MODELS if m in data]
    print("\nID | " + " | ".join(cols) + " | desc前60")
    for cid, c in q.items():
        vals = " | ".join(str(data[m].get(cid, {}).get("value")) for m in cols)
        print(f"{cid} | {vals} | {t(c.get('description'),60)}")

    weak, strong, common = [], [], []
    for cid, c in q.items():
        vals = {m: data[m].get(cid, {}).get("value") for m in cols}
        others = [vals[m] for m in cols if m != "qwen3.8-max-0902"]
        if any(v is not None and v > (vals["qwen3.8-max-0902"] or 0) for v in others):
            weak.append(cid)
        if vals["qwen3.8-max-0902"] == 1.0 and any(v is not None and v < 1.0 for v in others):
            strong.append(cid)
        if all(vals[m] is not None and vals[m] < 1 for m in cols):
            common.append(cid)
    print("\nqwen相对弱势ID:", weak)
    print("qwen强势ID:", strong)
    print("四模型全失分ID:", common)

    for cid in weak:
        c = q[cid]
        vals = {m: data[m].get(cid, {}).get("value") for m in cols}
        print(f"\n[弱] {cid} values={vals}")
        print(f"  desc(前220字): {t(c.get('description'),220)}")
        print(f"  qwen reasoning(前600字): {t(c.get('reasoning'),600)}")
        for m in cols:
            if m == "qwen3.8-max-0902":
                continue
            cc = data[m].get(cid)
            if cc and cc.get("value", 0) >= 1.0:
                print(f"  {m} reasoning(满分,前350字): {t(cc.get('reasoning'),350)}")
                break
    for cid in common:
        c = q[cid]
        print(f"\n[共失] {cid} (w={c.get('weight')}) desc(前160字): {t(c.get('description'),160)}")
        print(f"  qwen reasoning(前400字): {t(c.get('reasoning'),400)}")
