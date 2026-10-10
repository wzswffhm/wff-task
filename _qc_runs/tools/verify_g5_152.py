# -*- coding: utf-8 -*-
"""G5 判分核验（可指定 qwen/gpt/opus）：reward/计数/漂移/复算/未满分清单。
用法: python verify_g5_152.py [qwen|gpt|opus]
"""
import json
import pathlib
import sys

import tomllib

sys.stdout.reconfigure(encoding="utf-8")

WHICH = sys.argv[1] if len(sys.argv) > 1 else "qwen"
MAP = {
    "qwen": ("g5-152v4-qwen", "qwen38max-152v4", "qwen3.8-max-0902"),
    "gpt": ("g5-152v4-gpt", "gpt56sol-152v4", "gpt-5.6-sol"),
    "opus": ("g5-152v4-opus", "opus48-152v4", "claude-opus-4-8"),
}
if WHICH not in MAP:
    print(f"未知: {WHICH}（可选 {'/'.join(MAP)}）"); sys.exit(2)
out_dir, trial, model = MAP[WHICH]

Q = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\_qc_runs")
VER = Q / out_dir / "trials" / trial / "verifier"
TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152")

print("=" * 96)
print(f"G5 核验：{model}  ({out_dir}/{trial})")
print("=" * 96)

rj = VER / "reward.json"
if not rj.exists():
    print(f"  [!!] 缺 reward.json → {VER}"); sys.exit(1)
d = json.loads(rj.read_text(encoding="utf-8"))
print("  reward.json = " + json.dumps(d, ensure_ascii=False))
reward = d.get("reward"); counted = d.get("criteria_counted"); verr = d.get("verifier_error")

checks = []
checks.append(("reward 是正式值（非 fail-closed 占位）", not (reward in (0, 0.0) and verr == 1.0), f"reward={reward} err={verr}"))
checks.append(("criteria_counted == 40", counted == 40.0, f"{counted}"))
checks.append(("verifier_error == 0", verr in (0, 0.0), f"{verr}"))
rt = VER / "reward.txt"
if rt.exists():
    try:
        v = float(rt.read_text().strip())
        checks.append(("reward.txt == reward.json", abs(v - reward) < 1e-9, f"{v}"))
    except Exception as e:
        checks.append(("reward.txt 可解析", False, str(e)))
xm = VER / "reward_exit_message.json"
checks.append(("reward_exit_message 已删除（成功路径）", not xm.exists(), "存在" if xm.exists() else "已删"))

allok = True
for n, ok, e in checks:
    print(f"  [{'OK' if ok else '!!'}] {n}  ({e})")
    allok &= bool(ok)

print()
print("=" * 96)
print("判据零漂移 + 公式复算")
print("=" * 96)
rd = None
for c in [VER / "graded" / "reward-details.json", VER / "reward-details.json"]:
    if c.exists():
        rd = c; break
if not rd:
    print("  [!!] 缺 reward-details.json"); sys.exit(1)
j = json.loads(rd.read_text(encoding="utf-8"))
r = j.get("reward", j)
crit = r.get("criteria", [])
print(f"  details score={r.get('score')}  条数={len(crit)}")

t = tomllib.loads((TASK / "tests" / "rubrics.toml").read_text(encoding="utf-8"))
cur = {c["id"]: c for c in t["criterion"]}
bad_d = [cid for cid, c in
         ((c.get("id"), c) for c in crit)
         if cid not in cur or c.get("description") != cur[cid].get("description")]
bad_w = [c.get("id") for c in crit
         if c.get("id") in cur and float(c.get("weight", 0)) != float(cur[c["id"]].get("weight", 0))]
miss = [cid for cid in cur if cid not in {x.get("id") for x in crit}]
print(f"  description 漂移: {bad_d or '无（零漂移）'}")
print(f"  weight 漂移: {bad_w or '无'}")
print(f"  未判据条: {miss or '无'}")
if bad_d or bad_w or miss:
    allok = False

pos = [c for c in crit if not c.get("negate")]
neg = [c for c in crit if c.get("negate")]
sp = sum(float(c["weight"]) for c in pos)
num = sum(float(c["weight"]) * float(c.get("value", 0)) for c in pos)
den = sum(float(c["weight"]) * (1 - float(c.get("value", 0))) for c in neg)
calc = max(0.0, min(1.0, (num - den) / sp)) if sp else 0.0
same = abs(calc - reward) <= 1e-6
print(f"  复算={calc:.6f} vs reward={reward}  差={abs(calc-reward):.6f}  {'一致' if same else '!! 不一致'}")
if not same:
    allok = False

print()
print("=" * 96)
print("未满分判据（value < 1）")
print("=" * 96)
unf = []
for c in crit:
    v = c.get("value")
    if not (isinstance(v, (int, float)) and v >= 1):
        unf.append((c.get("id"), v, c.get("weight")))
        print(f"  {c.get('id'):<6} value={v} w={c.get('weight')}  {c.get('name','')[:50]}")
        rs = str(c.get("reasoning", ""))[:300].replace("\n", " ")
        print(f"         理由: {rs}")
print(f"  未满分 {len(unf)} 条 / 40 条   权重损失 ≈ {sum((1 - (v or 0)) * float(w or 0) for _, v, w in unf):.1f}")

print()
print("=" * 96)
print(f">>> {model}: reward={reward}  计数={counted}  err={verr}  {'核验通过' if allok else '核验有问题'}")
print("=" * 96)
sys.exit(0 if allok else 1)
