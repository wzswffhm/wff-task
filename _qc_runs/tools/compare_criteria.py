# -*- coding: utf-8 -*-
"""按数据组对齐四模型逐判据得分，找出 qwen 相对弱势/强势判据。"""
import json, sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")

# 数据组：名称 -> {模型: reward-details 路径（相对 ROOT）}
GROUPS = {
    "149-fix8(最新)": {
        "oracle":   r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹\oracle\reward-details.json",
        "qwen":     r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹\qwen3.8-max-0902\reward-details.json",
        "gpt":      r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹\gpt-5.6-sol\reward-details.json",
        "opus":     r"work_fin-b01_20261009_fix8-149\FIN3-WKN-149\跑分产物与轨迹\claude-opus-4-8\reward-details.json",
    },
    "149-fix7(旧,无后缀=当前; _prev=改前)": {
        "oracle":   r"work_fin-b01_20261005_fix7-149\跑分产物与轨迹\oracle\reward-details.json",
        "qwen":     r"work_fin-b01_20261005_fix7-149\跑分产物与轨迹\qwen3.8-max-0902\reward-details.json",
        "gpt":      r"work_fin-b01_20261005_fix7-149\跑分产物与轨迹\gpt-5.6-sol\reward-details.json",
        "opus":     r"work_fin-b01_20261005_fix7-149\跑分产物与轨迹\claude-opus-4-8\reward-details.json",
    },
    "150-fix6": {
        "oracle":   r"work_fin-b01_20261006_fix6-150\FIN3-WKN-150\跑分产物与轨迹\oracle\reward-details.json",
        "qwen":     r"work_fin-b01_20261006_fix6-150\FIN3-WKN-150\跑分产物与轨迹\qwen3.8-max-0902\reward-details.json",
        "gpt":      r"work_fin-b01_20261006_fix6-150\FIN3-WKN-150\跑分产物与轨迹\gpt-5.6-sol\reward-details.json",
        "opus":     r"work_fin-b01_20261006_fix6-150\FIN3-WKN-150\跑分产物与轨迹\claude-opus-4-8\reward-details.json",
    },
    "150-sync-backup(另一版判分)": {
        "oracle":   r"_qc_runs\sync150-backup-20261009-164347\oracle\reward-details.json",
        "qwen":     r"_qc_runs\sync150-backup-20261009-164347\qwen3.8-max-0902\reward-details.json",
        "gpt":      r"_qc_runs\sync150-backup-20261009-164347\gpt-5.6-sol\reward-details.json",
        "opus":     r"_qc_runs\sync150-backup-20261009-164347\claude-opus-4-8\reward-details.json",
    },
    "150-rejudge-before-tighten": {
        "oracle":   r"_qc_runs\rejudge150-before-tighten-20261009-123649\oracle\verifier\reward-details.json",
        "qwen":     r"_qc_runs\rejudge150-before-tighten-20261009-123649\qwen3.8-max-0902\verifier\reward-details.json",
        "gpt":      r"_qc_runs\rejudge150-before-tighten-20261009-123649\gpt-5.6-sol\verifier\reward-details.json",
        "opus":     r"_qc_runs\rejudge150-before-tighten-20261009-123649\claude-opus-4-8\verifier\reward-details.json",
    },
    "150-rejudge-final": {
        "oracle":   r"_qc_runs\rejudge150-final-20261009-170123\oracle\verifier\reward-details.json",
        "qwen":     r"_qc_runs\rejudge150-final-20261009-170123\qwen3.8-max-0902\verifier\reward-details.json",
        "gpt":      r"_qc_runs\rejudge150-final-20261009-170123\gpt-5.6-sol\verifier\reward-details.json",
        "opus":     r"_qc_runs\rejudge150-final-20261009-170123\claude-opus-4-8\verifier\reward-details.json",
    },
    "152v2(qwen/gpt/oracle)": {
        "oracle":   r"_qc_runs\g4-152v2\trials\oracle-152v2\verifier\reward-details.json",
        "qwen":     r"_qc_runs\g5-152v2-qwen2\trials\qwen38max2-152v2\verifier\reward-details.json",
        "gpt":      r"_qc_runs\g5-152v2-gpt5\trials\gpt56sol5-152v2\verifier\reward-details.json",
        "gpt-异常低": r"_qc_runs\g5-152v2-gpt\trials\gpt56sol-152v2\verifier\reward-details.json",
    },
    "152v3(qwen/gpt/oracle)": {
        "oracle":   r"_qc_runs\g4-152v3\trials\oracle-152v3\verifier\reward-details.json",
        "qwen":     r"_qc_runs\g5-152v3-qwen\trials\qwen38max-152v3\verifier\reward-details.json",
        "gpt":      r"_qc_runs\g5-152v3-gpt\trials\gpt56sol-152v3\verifier\reward-details.json",
    },
    "152v1(qwen/oracle仅两模型)": {
        "oracle":   r"_backup\work_fin-b01_20261009-152-v1\跑分产物与轨迹\oracle\reward-details.json",
        "qwen":     r"_backup\work_fin-b01_20261009-152-v1\跑分产物与轨迹\qwen3.8-max-0902\reward-details.json",
    },
    "FIN-PE-001(参考题)": {
        "oracle":   r"_reference\zq-金融-私募股权-20260930\跑分产物与轨迹\FIN-PE-001\oracle\reward-details.json",
        "qwen":     r"_reference\zq-金融-私募股权-20260930\跑分产物与轨迹\FIN-PE-001\qwen3.8-max-0902\reward-details.json",
        "gpt":      r"_reference\zq-金融-私募股权-20260930\跑分产物与轨迹\FIN-PE-001\gpt-5.6-sol\reward-details.json",
        "opus":     r"_reference\zq-金融-私募股权-20260930\跑分产物与轨迹\FIN-PE-001\claude-opus-4-8\reward-details.json",
    },
    "152初版(oracle/qwen, g5-152=qwen)": {
        "oracle":   r"_qc_runs\g4-152\trials\FIN3-WKN-152__Sa7ciyW\verifier\reward-details.json",
        "qwen":     r"_qc_runs\g5-152\trials\FIN3-WKN-152__vFbfvgm\verifier\reward-details.json",
    },
}

def load(rel):
    p = ROOT / rel
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def crit_map(d):
    r = d.get("reward", d)
    return {c["id"]: c for c in r.get("criteria", [])}, r.get("score")

def trunc(s, n):
    s = (s or "").replace("\n", " ").strip()
    return s[:n]

print("=" * 100)
for gname, mp in GROUPS.items():
    data = {}
    scores = {}
    ok = True
    for m, rel in mp.items():
        try:
            cm, sc = crit_map(load(rel))
            data[m] = cm
            scores[m] = sc
        except Exception as e:
            print(f"[组 {gname}] 模型 {m} 读取失败: {e}")
            ok = False
    if "qwen" not in data:
        print(f"\n### 组 [{gname}] 无 qwen 数据，跳过")
        continue
    print(f"\n\n########## 组 [{gname}] 总分: " +
          ", ".join(f"{m}={scores.get(m)}" for m in mp) + " ##########")
    q = data["qwen"]
    ids = list(q.keys())
    # 表头
    cols = [m for m in mp if m in data]
    print("ID | " + " | ".join(f"{m}" for m in cols) + " | 判据名")
    for cid in ids:
        vals = []
        for m in cols:
            c = data[m].get(cid)
            if c is None:
                vals.append("--")
            else:
                v = c.get("value")
                w = c.get("weight")
                vals.append(f"{v}(w{w})")
        name = q[cid].get("name", "")
        print(f"{cid} | " + " | ".join(vals) + f" | {trunc(name,60)}")

    # qwen 相对弱势：qwen value < max(gpt, opus) value
    print(f"\n--- [{gname}] qwen 相对失分判据（qwen < max(gpt,opus) 或 qwen<oracle 且其他>=oracle）---")
    weak = []
    strong = []
    for cid in ids:
        qc = q[cid]
        qv = qc.get("value")
        comps = {}
        for m in cols:
            if m in ("oracle",): continue
            c = data[m].get(cid)
            if c: comps[m] = c.get("value")
        others = [v for m, v in comps.items() if m != "qwen"]
        if not others: continue
        best = max(others)
        if best is not None and qv is not None and qv < best:
            weak.append(cid)
        if qv == 1.0 and any(v is not None and v < 1.0 for v in others):
            strong.append(cid)
    print("弱势ID:", weak)
    print("强势ID(qwen=1但其他<1):", strong)

    for cid in weak:
        qc = q[cid]
        print(f"\n  [弱] {cid} name={qc.get('name')} value分布: " +
              ", ".join(f"{m}={data[m].get(cid,{}).get('value')}" for m in cols if cid in data[m]))
        print(f"    description: {trunc(qc.get('description'),120)}")
        print(f"    qwen reasoning: {trunc(qc.get('reasoning'),300)}")
        # 打分更高的对手 reasoning
        for m in cols:
            if m == "qwen": continue
            c = data[m].get(cid)
            if c and c.get("value") == 1.0 and qc.get("value", 1) < 1.0:
                print(f"    {m} reasoning(得满分): {trunc(c.get('reasoning'),220)}")
                break
