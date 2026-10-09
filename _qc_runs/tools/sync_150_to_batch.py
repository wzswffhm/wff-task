# -*- coding: utf-8 -*-
"""把 FIN3-WKN-150 的 _rejudge 新判分同步到交付批次。

覆盖:
  <batch>/FIN3-WKN-150/跑分产物与轨迹/<ex>/reward.json
  <batch>/FIN3-WKN-150/跑分产物与轨迹/<ex>/reward-details.json
  <batch>/FIN3-WKN-150/跑分产物与轨迹/summary.json  (runs[].reward + mean)

不动: output/（交付物）、轨迹/（agent 轨迹）、task.toml（已是 A1）
备份到 _qc_runs/sync150-backup-<ts>/
"""
import json
import pathlib
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASK = "FIN3-WKN-150"
BATCH = W / "work-金融-私募股权投资-20261008" / TASK / "跑分产物与轨迹"
RJ = W / TASK / "_rejudge"
EXEC = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
BACKUP = W / "_qc_runs" / f"sync150-backup-{time.strftime('%Y%m%d-%H%M%S')}"
DRY = "--dry-run" in sys.argv


def read_reward(p):
    return json.loads(p.read_text(encoding="utf-8"))


# 1. 读 _rejudge 新分
new = {}
for e in EXEC:
    rj = RJ / e / "verifier" / "reward.json"
    rd = RJ / e / "verifier" / "reward-details.json"
    if not rj.is_file():
        raise SystemExit(f"缺 {rj}")
    new[e] = {
        "reward": read_reward(rj),
        "details": rd.read_bytes() if rd.is_file() else None,
    }
    print(f"  _rejudge {e}: reward={new[e]['reward']['reward']} counted={new[e]['reward']['criteria_counted']}")

# 2. 读交付批次旧分
print()
old = {}
for e in EXEC:
    rj = BATCH / e / "reward.json"
    if rj.is_file():
        old[e] = read_reward(rj)["reward"]
        print(f"  交付批次 {e}: 旧 reward={old[e]}")

# 3. G5 均分
def g5(d):
    return (d["qwen3.8-max-0902"]["reward"]["reward"] +
            d["claude-opus-4-8"]["reward"]["reward"] +
            d["gpt-5.6-sol"]["reward"]["reward"]) / 3

new_g5 = g5(new)
print(f"\n  新 G5 三模型均分 = {new_g5:.6f}  ({'< 0.70 PASS' if new_g5 < 0.7 else '>= 0.70 FAIL'})")
print(f"  新 G4 oracle      = {new['oracle']['reward']['reward']:.6f}  ({'> 0.85 PASS' if new['oracle']['reward']['reward'] > 0.85 else 'FAIL'})")

if DRY:
    print("\n[dry-run] 不写入")
    sys.exit(0)

# 4. 备份
if not BACKUP.is_dir():
    BACKUP.mkdir(parents=True)
    for e in EXEC:
        (BACKUP / e).mkdir(exist_ok=True)
        for name in ("reward.json", "reward-details.json"):
            s = BATCH / e / name
            if s.is_file():
                shutil.copy2(s, BACKUP / e / name)
    shutil.copy2(BATCH / "summary.json", BACKUP / "summary.json")
    print(f"\n备份到 {BACKUP}")

# 5. 覆盖 reward.json + reward-details.json
print("\n同步:")
for e in EXEC:
    dst = BATCH / e
    # reward.json
    src_rj = RJ / e / "verifier" / "reward.json"
    shutil.copy2(src_rj, dst / "reward.json")
    print(f"  {e}/reward.json <- _rejudge ({new[e]['reward']['reward']})")
    # reward-details.json
    if new[e]["details"]:
        shutil.copy2(RJ / e / "verifier" / "reward-details.json", dst / "reward-details.json")
        print(f"  {e}/reward-details.json <- _rejudge ({len(new[e]['details']):,} B)")

# 6. 更新 summary.json
sp = BATCH / "summary.json"
summ = json.loads(sp.read_text(encoding="utf-8"))
for run in summ["runs"]:
    m = run["model"]
    if m in new:
        run["reward"] = new[m]["reward"]["reward"]
        run["criteria_counted"] = new[m]["reward"]["criteria_counted"]
        run["scored"] = True
        run["verifier_error"] = new[m]["reward"].get("verifier_error", 0.0)
summ["mean"] = round(new_g5, 6)
summ["mean_gate"] = "<0.70"
summ["gate_pass"] = new_g5 < 0.70
summ["declared_difficulty"] = "A1"
# 轮次标记
summ["round"] = summ.get("round", "") + "+tighten-r29r30"
sp.write_text(json.dumps(summ, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n  summary.json: mean={summ['mean']} gate_pass={summ['gate_pass']} round={summ['round']}")

# 7. 校验
print("\n校验:")
ok = True
for e in EXEC:
    cur = read_reward(BATCH / e / "reward.json")["reward"]
    exp = new[e]["reward"]["reward"]
    match = abs(cur - exp) < 1e-9
    ok = ok and match
    print(f"  {e}: {cur} {'==' if match else '!='} {exp}")
final_g5 = g5({e: {"reward": {"reward": read_reward(BATCH / e / 'reward.json')['reward']}} for e in EXEC})
print(f"  交付批次 G5 = {final_g5:.6f}  {'PASS' if final_g5 < 0.7 else 'FAIL'}")
print(f"\n>>> 同步{'成功' if ok else '有差异'}")
