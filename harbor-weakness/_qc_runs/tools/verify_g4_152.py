# -*- coding: utf-8 -*-
"""G4 判分核验：reward 门槛 / 计数 / 漂移 / 未满分清单。"""
import json
import pathlib
import sys

import tomllib

sys.stdout.reconfigure(encoding="utf-8")

Q = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\_qc_runs\g4-152v4")
T = Q / "trials" / "oracle-152v4"
TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152")
VER = T / "verifier"

print("=" * 96)
print("1) reward.json（最终值，非占位）")
print("=" * 96)
rj = VER / "reward.json"
if not rj.exists():
    print("  [!!] 缺 reward.json"); sys.exit(1)
d = json.loads(rj.read_text(encoding="utf-8"))
print("  " + json.dumps(d, ensure_ascii=False))
reward = d.get("reward")
counted = d.get("criteria_counted")
verr = d.get("verifier_error")

print()
print("=" * 96)
print("2) 门禁判定")
print("=" * 96)
checks = [
    ("reward >= 0.85（G4 门槛）", isinstance(reward, (int, float)) and reward >= 0.85, f"{reward}"),
    ("criteria_counted == 40", counted == 40.0, f"{counted}"),
    ("verifier_error == 0", verr in (0, 0.0), f"{verr}"),
]
# reward.txt 一致性
rt = VER / "reward.txt"
if rt.exists():
    try:
        v = float(rt.read_text().strip())
        checks.append(("reward.txt == reward.json.reward", abs(v - reward) < 1e-9, f"{v} vs {reward}"))
    except Exception as e:
        checks.append(("reward.txt 可解析", False, str(e)))
# fail-closed 消息应已删除
xm = VER / "reward_exit_message.json"
if xm.exists():
    try:
        j = json.loads(xm.read_text(encoding="utf-8"))
        checks.append(("reward_exit_message 已删除（成功路径）", False, str(j)[:120]))
    except Exception:
        checks.append(("reward_exit_message", False, "存在"))
else:
    checks.append(("reward_exit_message 已删除（成功路径）", True, "不存在"))

allok = True
for name, ok, extra in checks:
    print(f"  [{'OK' if ok else '!!'}] {name}   ({extra})")
    allok &= bool(ok)

print()
print("=" * 96)
print("3) 判据零漂移（reward-details vs 现行 rubrics.toml）")
print("=" * 96)
rd = None
for cand in [VER / "graded" / "reward-details.json", VER / "reward-details.json"]:
    if cand.exists():
        rd = cand
        break
if not rd:
    print("  [!!] 缺 reward-details.json")
    allok = False
else:
    j = json.loads(rd.read_text(encoding="utf-8"))
    r = j.get("reward", j)
    crit = r.get("criteria", [])
    print(f"  details score={r.get('score')}  条数={len(crit)}")
    t = tomllib.loads((TASK / "tests" / "rubrics.toml").read_text(encoding="utf-8"))
    cur = {c["id"]: c for c in t["criterion"]}
    bad_d, bad_w = [], []
    for c in crit:
        cid = c.get("id")
        if cid not in cur:
            bad_d.append(f"{cid}(现行无此条)")
            continue
        if c.get("description") != cur[cid].get("description"):
            bad_d.append(cid)
        if float(c.get("weight", 0)) != float(cur[cid].get("weight", 0)):
            bad_w.append(cid)
    miss = [cid for cid in cur if cid not in {x.get("id") for x in crit}]
    print(f"  description 漂移: {bad_d or '无（零漂移）'}")
    print(f"  weight 漂移: {bad_w or '无'}")
    print(f"  判据缺失(未判): {miss or '无'}")
    if bad_d or bad_w or miss:
        allok = False
    # 按 rewardkit 公式复算
    pos = [c for c in crit if not c.get("negate")]
    neg = [c for c in crit if c.get("negate")]
    sp = sum(float(c["weight"]) for c in pos)
    num = sum(float(c["weight"]) * float(c.get("value", 0)) for c in pos)
    den = sum(float(c["weight"]) * (1 - float(c.get("value", 0))) for c in neg)
    calc = max(0.0, min(1.0, (num - den) / sp)) if sp else 0
    print(f"  复算(公式)={calc:.6f}  vs reward.json={reward}  差={abs(calc-reward):.6f}")
    if abs(calc - reward) > 1e-6:
        print("  [!!] 复算不一致")
        allok = False
    else:
        print("  [OK] 复算一致")

    print()
    print("=" * 96)
    print("4) 逐条得分（未满分高亮）")
    print("=" * 96)
    unf = []
    for c in crit:
        v = c.get("value")
        mark = "" if (isinstance(v, (int, float)) and v >= 1) else "   <== 未满分"
        if mark:
            unf.append(c.get("id"))
        print(f"  {c.get('id'):<6} value={v}  w={c.get('weight')}  {c.get('name','')[:40]}{mark}")
    print(f"  未满分 {len(unf)} 条: {unf or '无（全对）'}")

print()
print("=" * 96)
print((">>> G4 通过（reward=%.6f）—— 可启动 G5 qwen+gpt" % reward)
      if (allok and isinstance(reward, (int, float)) and reward >= 0.85)
      else ">>> G4 未达标，不要启动 G5")
print("=" * 96)
sys.exit(0 if allok else 1)
