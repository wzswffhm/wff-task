# -*- coding: utf-8 -*-
"""汇总所有 reward-details.json，按题目/批次分组，对比四模型逐判据得分。"""
import json, os, sys, io, re
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
MODELS = ["oracle", "qwen3.8-max-0902", "gpt-5.6-sol", "claude-opus-4-8"]

def find_model(p: Path):
    parts = [x.lower() for x in p.parts]
    s = str(p).lower()
    for m in MODELS:
        if m in s:
            return m
    # trial 名缩写
    if "qwen" in s:
        return "qwen3.8-max-0902"
    if "gpt" in s:
        return "gpt-5.6-sol"
    if "opus" in s:
        return "claude-opus-4-8"
    if "oracle" in s:
        return "oracle"
    return None

def load(p: Path):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"__error__": str(e)}

def extract(d):
    """返回 (score, criteria list, kind)"""
    if not isinstance(d, dict):
        return None, [], None
    r = d.get("reward", d)
    if not isinstance(r, dict):
        return None, [], None
    score = r.get("score")
    crit = r.get("criteria") or []
    kind = r.get("kind")
    return score, crit, kind

files = sorted(ROOT.rglob("reward-details.json"))
rows = []
for p in files:
    model = find_model(p)
    data = load(p)
    score, crit, kind = extract(data)
    # 归组：取路径中特征段
    rel = p.relative_to(ROOT)
    rows.append({
        "path": str(rel),
        "model": model,
        "score": score,
        "n": len(crit),
        "kind": kind,
        "crit": crit,
        "has_judge": all(("reasoning" in c) for c in crit) if crit else False,
    })

print(f"共找到 {len(files)} 个 reward-details.json\n")
for r in rows:
    print(f"{r['model'] or '?':<18} score={r['score']!s:<6} n={r['n']:<3} kind={r['kind']!s:<14} {r['path']}")
