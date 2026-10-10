# -*- coding: utf-8 -*-
"""从 reward-details.json 中抽取指定判据的得分与判官理由（验证核心整改）。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness"
                    r"\work_fin-b01_20261006_fix6-150\FIN3-WKN-150\跑分产物与轨迹")


def walk(o):
    if isinstance(o, dict):
        if "description" in o and "value" in o and "id" in o:
            yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def items(ex):
    d = json.loads((BASE / ex / "reward-details.json").read_text(encoding="utf-8"))
    out, seen = [], set()
    for it in walk(d):
        k = (it["id"], it.get("description", "")[:40])
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


for ex in ("oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"):
    its = items(ex)
    bad = [i for i in its if float(i.get("value") or 0) < 1.0]
    print(f"=== {ex}: 条目 {len(its)}，未满分 {len(bad)} ===")
    for i in bad:
        print(f"   {i['id']:5} value={i['value']} raw={i.get('raw')} "
              f"w={i.get('weight')}  {i.get('description', '')[:46]}")
    for i in its:
        if "调整后 EBITDA 还原正确" in i.get("description", "") or "扣非归母净利润还原正确" in i.get("description", ""):
            print(f"   [{i['id']}] value={i['value']} raw={i.get('raw')} w={i.get('weight')}")
            print(f"       理由: {str(i.get('reasoning'))[:420]}")
    print()
