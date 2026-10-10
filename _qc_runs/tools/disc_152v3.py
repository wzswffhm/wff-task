# -*- coding: utf-8 -*-
"""152 v3 判据区分度分析：哪些判据全员满分（压不了均分），哪些有区分度。
数据源：g4-152v3 / g5-152v3-{qwen,gpt,opus} 的 reward-details.json
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

Q = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\_qc_runs")

SRC = {
    "oracle": Q / "g4-152v3" / "trials" / "oracle-152v3" / "verifier",
    "qwen": Q / "g5-152v3-qwen" / "trials" / "qwen38max-152v3" / "verifier",
    "gpt": Q / "g5-152v3-gpt" / "trials" / "gpt56sol-152v3" / "verifier",
    "opus": Q / "g5-152v3-opus" / "trials" / "opus48-152v3" / "verifier",
}

data = {}
for name, d in SRC.items():
    f = d / "reward-details.json"
    if not f.exists():
        # 找 graded 子目录
        cands = list(d.rglob("reward-details.json")) if d.exists() else []
        f = cands[0] if cands else None
    if f and f.exists():
        j = json.loads(f.read_text(encoding="utf-8"))
        r = j.get("reward", j)
        crits = r.get("criteria", [])
        data[name] = {c["id"]: c for c in crits}
        print(f"  {name:<7} {f}  {len(crits)} 条  score={r.get('score')}")
    else:
        print(f"  {name:<7} (无 reward-details) —— {d}")

print()
print("=" * 110)
print("逐判据得分矩阵（value；opus 缺失表示 verifier 未跑完）")
print("=" * 110)
allids = []
for m in data.values():
    for i in m:
        if i not in allids:
            allids.append(i)

hdr = f"{'ID':<6}{'w':>5} {'oracle':>7}{'qwen':>7}{'gpt':>7}{'opus':>7}   {'name/description 摘要'}"
print(hdr)
print("-" * 110)

full = []      # 所有可用执行体都满分（无区分度）
partial = []   # 有区分度
for cid in allids:
    vals = {}
    for ex in ("oracle", "qwen", "gpt", "opus"):
        c = data.get(ex, {}).get(cid)
        vals[ex] = c.get("value") if c else None
    ref = data.get("oracle", {}).get(cid)
    w = ref.get("weight") if ref else "?"
    name = (ref or {}).get("name", "")
    desc = (ref or {}).get("description", "")
    brief = (name or desc)[:70].replace("\n", " ")
    row = f"{cid:<6}{str(w):>5} "
    for ex in ("oracle", "qwen", "gpt", "opus"):
        v = vals[ex]
        row += f"{('—' if v is None else v):>7}"
    row += f"   {brief}"
    print(row)

    # 判定区分度：qwen/gpt 是否满分（最高档=5 或 weight 对应满分）
    avail = [v for k, v in vals.items() if k in ("oracle", "qwen", "gpt") and v is not None]
    if avail:
        mx = max(avail)
        if all(v == mx for v in avail):
            full.append(cid)
        else:
            partial.append(cid)

print()
print("=" * 110)
print(f"全员同分（无区分度，压不了均分）: {len(full)} 条 -> {full}")
print(f"有区分度: {len(partial)} 条 -> {partial}")
print("=" * 110)

# qwen 满分/非满分的价值分档
print()
print("说明：value 满档通常为 5（likert）或 weight 对应分值；需结合 description 判断。")
for ex in ("oracle", "qwen", "gpt"):
    if ex in data:
        items = data[ex]
        tot = sum(c.get("weight", 0) for c in items.values() if not c.get("negate"))
        got = sum(c.get("weight", 0) * (c.get("value", 0) / 5.0) for c in items.values()
                  if not c.get("negate") and isinstance(c.get("value"), (int, float)))
        print(f"  {ex}: 正分加权近似 {got:.2f} / {tot}")
