# -*- coding: utf-8 -*-
"""采集 282/FIN3-WKN-152 的交付就绪状态：飞书记录 + v1/v2/v3 跑分结果 + 题包结构。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
Q = W / "harbor-weakness" / "_qc_runs"
TASK = W / "harbor-weakness" / "FIN3-WKN-152"

print("=" * 100)
print("1) 飞书 序号 282 记录")
print("=" * 100)
try:
    data = json.loads((Q / "feishu_weakness_all.json").read_text(encoding="utf-8-sig"))
    recs = data.get("data", {}).get("items") or data.get("records") or []
    for r in recs:
        f = r.get("fields", {})
        no = f.get("序号")
        if no == 282 or str(no) == "282":
            def txt(v):
                if isinstance(v, list):
                    return " | ".join(
                        (i.get("text", "") if isinstance(i, dict) else str(i)) for i in v
                    ) if v and isinstance(v[0], dict) else json.dumps(v, ensure_ascii=False)
                if isinstance(v, dict):
                    return json.dumps(v, ensure_ascii=False)
                return str(v)
            for k, v in f.items():
                s = txt(v)
                if len(s) > 300:
                    s = s[:300] + f" …(共{len(txt(v))}字)"
                print(f"  {k}: {s}")
            print(f"  record_id: {r.get('record_id')}")
            break
except Exception as e:
    print(f"  解析失败: {e}")

print()
print("=" * 100)
print("2) 各轮跑分 reward.json（g4=oracle, g5=三模型）")
print("=" * 100)
for d in sorted(Q.glob("*152*")):
    if not d.is_dir():
        continue
    rj = list(d.rglob("reward.json"))
    if not rj:
        print(f"  {d.name:<26} (无 reward.json)")
        continue
    parts = []
    for f in rj:
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
            parts.append(
                f"{f.parent.parent.name}:reward={j.get('reward')},counted={j.get('criteria_counted')},err={j.get('verifier_error')}"
            )
        except Exception as e:
            parts.append(f"{f.parent.parent.name}:ERR {e}")
    print(f"  {d.name:<26} {len(rj)} 个")
    for p in parts:
        print(f"      {p}")

print()
print("=" * 100)
print("3) 批次归档 summary.json（若有）")
print("=" * 100)
for f in sorted(Q.rglob("summary.json")):
    if "152" not in str(f):
        continue
    try:
        s = json.loads(f.read_text(encoding="utf-8"))
        print(f"  {f.relative_to(Q)}")
        for k in ("task_version", "round", "mean", "gate", "gate_pass", "declared_difficulty", "scored_at"):
            if k in s:
                print(f"      {k}: {s[k]}")
        for r in s.get("runs", []):
            print(f"      run {r.get('executor')}: reward={r.get('reward')}")
    except Exception as e:
        print(f"  {f} ERR {e}")

print()
print("=" * 100)
print("4) 题包目录 FIN3-WKN-152 顶层与可疑残留")
print("=" * 100)
for p in sorted(TASK.iterdir()):
    if p.is_dir():
        n = sum(1 for x in p.rglob("*") if x.is_file())
        print(f"  [dir ] {p.name}/  ({n} 文件)")
    else:
        print(f"  [file] {p.name}  ({p.stat().st_size:,} B)")
print()
tests = TASK / "tests"
for p in sorted(tests.iterdir()):
    n = sum(1 for x in p.rglob("*") if x.is_file()) if p.is_dir() else 1
    print(f"  tests/{p.name}{'/' if p.is_dir() else ''}  ({n})")

print()
print("=" * 100)
print("5) 已打包 zip 与批次目录")
print("=" * 100)
for z in sorted((Q / "packages").glob("*152*")):
    import datetime
    mt = datetime.datetime.fromtimestamp(z.stat().st_mtime).strftime("%m-%d %H:%M")
    print(f"  {z.name:<40} {z.stat().st_size:>10,} B  {mt}")
for d in sorted((W / "harbor-weakness").glob("work*152*")):
    print(f"  [dir] {d.name}")
