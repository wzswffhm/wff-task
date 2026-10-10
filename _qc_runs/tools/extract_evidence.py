# -*- coding: utf-8 -*-
"""提取 qwen 弱势/强势判据的完整证据文本 + 检查 151 zip + summary.json。"""
import json, sys, io, zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")

def load(rel):
    with open(ROOT / rel, "r", encoding="utf-8") as f:
        return json.load(f)

def cm(rel):
    d = load(rel)
    r = d.get("recipient", d) if False else d.get("reward", d)
    return {c["id"]: c for c in r.get("criteria", [])}, r.get("score")

def t(s, n):
    return (s or "").replace("\n", " ").strip()[:n]

# 弱势判据明细（组名, 路径dict, 弱势ID列表）
CASES = [
    ("149-fix8", r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹", ["R08"]),
    ("150-rejudge-final(=150-fix6判分)", r"_qc_runs\rejudge150-final-20261009-170123", ["R10", "R19", "R28", "R31"]),
    ("150-before-tighten", r"_qc_runs\rejudge150-before-tighten-20261009-123649", ["R13", "R19", "R23"]),
    ("150-sync-backup", r"_qc_runs\sync150-backup-20261009-164347", ["R21", "R22"]),
    ("FIN-PE-001", r"_reference\zq-金融-私募股权-20260930\跑分产物与轨迹\FIN-PE-001", ["R12", "R37"]),
]
REL = {
    "149-fix8": {
        "oracle": r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹\oracle\reward-details.json",
        "qwen":   r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹\qwen3.8-max-0902\reward-details.json",
        "gpt":    r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹\gpt-5.6-sol\reward-details.json",
        "opus":   r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹\claude-opus-4-8\reward-details.json",
    },
    "150-rejudge-final(=150-fix6判分)": {
        "oracle": r"_qc_runs\rejudge150-final-20261009-170123\oracle\verifier\reward-details.json",
        "qwen":   r"_qc_runs\rejudge150-final-20261009-170123\qwen3.8-max-0902\verifier\reward-details.json",
        "gpt":    r"_qc_runs\rejudge150-final-20261009-170123\gpt-5.6-sol\verifier\reward-details.json",
        "opus":   r"_qc_runs\rejudge150-final-20261009-170123\claude-opus-4-8\verifier\reward-details.json",
    },
    "150-before-tighten": {
        "oracle": r"_qc_runs\rejudge150-before-tighten-20261009-123649\oracle\verifier\reward-details.json",
        "qwen":   r"_qc_runs\rejudge150-before-tighten-20261009-123649\qwen3.8-max-0902\verifier\reward-details.json",
        "gpt":    r"_qc_runs\rejudge150-before-tighten-20261009-123649\gpt-5.6-sol\verifier\reward-details.json",
        "opus":   r"_qc_runs\rejudge150-before-tighten-20261009-123649\claude-opus-4-8\verifier\reward-details.json",
    },
    "150-sync-backup": {
        "oracle": r"_qc_runs\sync150-backup-20261009-164347\oracle\reward-details.json",
        "qwen":   r"_qc_runs\sync150-backup-20261009-164347\qwen3.8-max-0902\reward-details.json",
        "gpt":    r"_qc_runs\sync150-backup-20261009-164347\gpt-5.6-sol\reward-details.json",
        "opus":   r"_qc_runs\sync150-backup-20261009-164347\claude-opus-4-8\reward-details.json",
    },
    "FIN-PE-001": {
        "oracle": r"_reference\zq-金融-私募股权-20260930\跑分产物与轨迹\FIN-PE-001\oracle\reward-details.json",
        "qwen":   r"_reference\zq-金融-私募股权-20260930\跑分产物与轨迹\FIN-PE-001\qwen3.8-max-0902\reward-details.json",
        "gpt":    r"_reference\zq-金融-私募股权-20260930\跑分产物与轨迹\FIN-PE-001\gpt-5.6-sol\reward-details.json",
        "opus":   r"_reference\zq-金融-私募股权-20260930\跑分产物与轨迹\FIN-PE-001\claude-opus-4-8\reward-details.json",
    },
}

print("=" * 90)
print("第一部分：qwen 相对弱势判据完整证据")
print("=" * 90)
for gname, ids in [(c[0], c[2]) for c in CASES]:
    data = {m: cm(rel)[0] for m, rel in REL[gname].items()}
    print(f"\n##### 组 [{gname}] #####")
    for cid in ids:
        q = data["qwen"][cid]
        vals = {m: data[m].get(cid, {}).get("value") for m in data}
        print(f"\n--- {cid}  value: {vals}")
        print(f"  description(前240字): {t(q.get('description'),240)}")
        print(f"  qwen reasoning(前600字): {t(q.get('reasoning'),600)}")
        for m in ("gpt", "opus"):
            c = data[m].get(cid)
            if c and c.get("value", 0) >= 1.0:
                print(f"  {m} reasoning(满分,前400字): {t(c.get('reasoning'),400)}")
                break
        # raw 字段
        print(f"  qwen raw={q.get('raw')!r}, weight={q.get('weight')}")

print("\n\n" + "=" * 90)
print("第二部分：qwen 强势判据（qwen=1 而 gpt 或 opus <1）的 description 与对手失分证据")
print("=" * 90)
STRONG_CASES = [
    ("149-fix8", ["R05", "R09", "R10", "R16", "R17", "R18", "R19", "R28", "R29"]),
    ("150-rejudge-final(=150-fix6判分)", ["R03", "R06", "R08", "R13", "R21", "R23", "R24", "R25", "R26", "R27", "R32", "N01", "N02"]),
    ("FIN-PE-001", ["R19"]),
]
for gname, ids in STRONG_CASES:
    data = {m: cm(rel)[0] for m, rel in REL[gname].items()}
    print(f"\n##### 组 [{gname}] #####")
    for cid in ids:
        q = data["qwen"][cid]
        vals = {m: data[m].get(cid, {}).get("value") for m in data}
        print(f"\n--- {cid}  value: {vals}")
        print(f"  description(前180字): {t(q.get('description'),180)}")
        for m in ("gpt", "opus"):
            c = data[m].get(cid)
            if c and c.get("value", 1) < 1.0:
                print(f"  {m} reasoning(失分,前350字): {t(c.get('reasoning'),350)}")
                break

# 三模型全挂但 oracle 满分的判据（对压均分有用的"共性难题"）
print("\n\n" + "=" * 90)
print("第三部分：qwen<1 且 gpt<1 且 opus<1（三模型共同失分，oracle=1）")
print("=" * 90)
for gname in REL:
    data = {m: cm(rel)[0] for m, rel in REL[gname].items()}
    if not all(m in data for m in ("oracle", "qwen", "gpt", "opus")):
        continue
    print(f"\n##### 组 [{gname}] #####")
    for cid in data["qwen"]:
        vals = {m: data[m].get(cid, {}).get("value") for m in ("oracle", "qwen", "gpt", "opus")}
        if vals["oracle"] == 1.0 and all(vals[m] is not None and vals[m] < 1 for m in ("qwen", "gpt", "opus")):
            w = data["qwen"][cid].get("weight")
            print(f"  {cid} (w={w}) values={vals} desc: {t(data['qwen'][cid].get('description'),100)}")

# 151 zip 检查
print("\n\n" + "=" * 90)
print("第四部分：FIN3-WKN-151 是否有跑分产物（检查 zip 内文件列表）")
print("=" * 90)
for zname in ["FIN3-WKN-151_answer.zip", "FIN3-WKN-151_task.zip", "work_fin-b01_20261006-151.zip"]:
    zp = ROOT / zname
    if not zp.exists():
        print(f"{zname}: 不存在")
        continue
    try:
        with zipfile.ZipFile(zp) as z:
            names = z.namelist()
            hit = [n for n in names if "reward" in n.lower()]
            print(f"{zname}: 共{len(names)}个条目, reward相关={hit[:10]}")
    except Exception as e:
        print(f"{zname}: 打开失败 {e}")

# summary.json 内容
print("\n\n" + "=" * 90)
print("第五部分：summary.json 中的四模型分数")
print("=" * 90)
for rel in [
    r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹\summary.json",
    r"work_fin-b01_20261006_fix6-150\FIN3-WKN-150\跑分产物与轨迹\summary.json",
    r"_qc_runs\sync150-backup-20261009-164347\summary.json",
    r"_backup\work_fin-b01_20261009-152-v1\跑分产物与轨迹\summary.json",
    r"work_fin-b01_20261005_fix7-149\跑分产物与轨迹\summary.json",
]:
    try:
        d = load(rel)
        print(f"\n[{rel}] keys={list(d.keys())[:8]}")
        print(json.dumps(d, ensure_ascii=False, indent=1)[:1500])
    except Exception as e:
        print(f"[{rel}] 读取失败: {e}")
