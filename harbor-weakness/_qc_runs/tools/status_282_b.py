# -*- coding: utf-8 -*-
"""282 交付体检第 2 步：飞书记录 + 批次目录 + 当前题包判据 + opus 失败原因 + 残留对比。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = W / "harbor-weakness" / "FIN3-WKN-152"
BATCH = W / "harbor-weakness" / "work_fin-b01_20261009-152"
Q = W / "harbor-weakness" / "_qc_runs"

print("=" * 100)
print("1) 飞书 序号 282")
print("=" * 100)
fp = W / "_qc_runs" / "feishu_weakness_all.json"
if fp.exists():
    data = json.loads(fp.read_text(encoding="utf-8-sig"))
    items = data.get("data", {}).get("items") or data.get("records") or data.get("items") or []
    hit = False
    for r in items:
        f = r.get("fields", {})
        no = f.get("序号")
        if str(no) == "282":
            hit = True
            def txt(v):
                if isinstance(v, list):
                    if v and isinstance(v[0], dict):
                        return " | ".join(i.get("text", str(i)) for i in v)
                    return json.dumps(v, ensure_ascii=False)
                if isinstance(v, dict):
                    return json.dumps(v, ensure_ascii=False)
                return str(v)
            for k, v in f.items():
                s = txt(v)
                if len(s) > 400:
                    s = s[:400] + f" …(共{len(txt(v))}字)"
                print(f"  {k}: {s}")
            print(f"  record_id: {r.get('record_id')}")
    if not hit:
        print(f"  未找到 282，共 {len(items)} 条记录")
        for r in items[:60]:
            f = r.get("fields", {})
            print(f"    序号={f.get('序号')} 状态={f.get('状态')} 难度={f.get('题目难度')}")
else:
    print(f"  文件不存在: {fp}")

print()
print("=" * 100)
print("2) 批次目录 work_fin-b01_20261009-152")
print("=" * 100)
if BATCH.exists():
    for p in sorted(BATCH.iterdir()):
        if p.is_dir():
            n = sum(1 for x in p.rglob("*") if x.is_file())
            print(f"  [dir ] {p.name}/ ({n} 文件)")
        else:
            print(f"  [file] {p.name} ({p.stat().st_size:,} B)")
    inner = BATCH / "FIN3-WKN-152"
    if inner.exists():
        for p in sorted(inner.iterdir()):
            if p.is_dir():
                n = sum(1 for x in p.rglob("*") if x.is_file())
                print(f"      [dir ] {p.name}/ ({n})")
            else:
                print(f"      [file] {p.name} ({p.stat().st_size:,} B)")
    arch = inner / "跑分产物与轨迹"
    if arch.exists():
        print("      --- 跑分产物与轨迹 ---")
        for p in sorted(arch.iterdir()):
            print(f"        {p.name}{'/' if p.is_dir() else ''}")
        s = arch / "summary.json"
        if s.exists():
            j = json.loads(s.read_text(encoding="utf-8"))
            for k, v in j.items():
                if k != "runs":
                    print(f"          {k}: {v}")
            for r in j.get("runs", []):
                print(f"          run: {r}")

print()
print("=" * 100)
print("3) 当前题包判据状态")
print("=" * 100)
import tomllib
rb = TASK / "tests" / "rubrics.toml"
rj = TASK / "rubrics.json"
if rb.exists():
    t = tomllib.loads(rb.read_text(encoding="utf-8"))
    crit = t.get("criterion", [])
    pos = [c for c in crit if not c.get("negate")]
    neg = [c for c in crit if c.get("negate")]
    smax = sum(float(c.get("weight", 0)) for c in pos)
    print(f"  rubrics.toml: {len(crit)} 条（正 {len(pos)} / 负 {len(neg)}）S_max={smax}")
    print(f"  判据ID: {[c['id'] for c in crit]}")
if rj.exists():
    j = json.loads(rj.read_text(encoding="utf-8"))
    items = j.get("items") or j.get("criteria") or []
    print(f"  rubrics.json: {len(items)} 条")
    if items and isinstance(items[0], dict):
        print(f"  json IDs: {[i.get('id') for i in items]}")

print()
print("=" * 100)
print("4) v3 opus 失败原因")
print("=" * 100)
for d in [Q / "g5-152v3-opus"]:
    if d.exists():
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix in (".json", ".txt", ".log") and f.stat().st_size < 3_000_000:
                rel = f.relative_to(d).as_posix()
                print(f"  {rel}  ({f.stat().st_size:,} B)")
        # 读关键 json
        for name in ["reward_exit_message.json", "reward.json"]:
            for f in d.rglob(name):
                try:
                    print(f"  --- {f.relative_to(d).as_posix()} ---")
                    print("      " + f.read_text(encoding="utf-8")[:1200].replace("\n", "\n      "))
                except Exception as e:
                    print(f"  {f} 读失败 {e}")

print()
print("=" * 100)
print("5) tests/__golden_output__ 残留对比")
print("=" * 100)
a = TASK / "tests" / "__golden_output"
b = TASK / "tests" / "__golden_output__"
if a.exists() and b.exists():
    fa = {p.name: p.stat().st_size for p in a.iterdir() if p.is_file()}
    fb = {p.name: p.stat().st_size for p in b.iterdir() if p.is_file()}
    print(f"  __golden_output  : {sorted(fa)}")
    print(f"  __golden_output__: {sorted(fb)}")
    import hashlib
    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    for name in sorted(set(fa) | set(fb)):
        pa, pb = a / name, b / name
        if pa.exists() and pb.exists():
            same = sha(pa) == sha(pb)
            print(f"    {name:<45} {'一致' if same else '不一致!!'}")
        else:
            print(f"    {name:<45} 仅单侧存在")
    print(f"  solution/golden_output 文件: {sorted(p.name for p in (TASK/'solution'/'golden_output').iterdir())}")
else:
    print(f"  a={a.exists()} b={b.exists()}")
