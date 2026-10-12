# -*- coding: utf-8 -*-
"""FIN3-WKN-153 跑分归档：把 G4/G5 的 trial 产物归档到批次根 `跑分产物与轨迹/`。

- oracle            ← _qc_runs/g4-153/trials/oracle-153
- qwen3.8-max-0902  ← _qc_runs/g5-153-qwen/trials/qwen38max-153
- gpt-5.6-sol       ← _qc_runs/g5-153-gpt/trials/gpt56sol-153
- claude-opus-4-8   ← _qc_runs/g5-153-opus/trials/opus48-153

用法：python archive_153.py             # 归档已完成的 run 并重建 summary
      python archive_153.py --summary   # 只重建 summary.json
"""
import json
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
BATCH = H / "work_fin-b01_20261012-153"
TASK = "FIN3-WKN-153"
DST = BATCH / "跑分产物与轨迹"
Q = H / "_qc_runs"

RUNS = [
    ("oracle", Q / "g4-153" / "trials", ["oracle-153"]),
    ("qwen3.8-max-0902", Q / "g5-153-qwen" / "trials",
     ["qwen38max-153-reg1", "qwen38max-153"]),
    ("gpt-5.6-sol", Q / "g5-153-gpt" / "trials", ["gpt56sol-153"]),
    ("claude-opus-4-8", Q / "g5-153-opus" / "trials", ["opus48-153"]),
]


def pick_trial(trials_dir: pathlib.Path, names):
    """优先返回 verifier_error=0 且带 reward 的 trial；否则取第一个存在的。"""
    cands = [trials_dir / n for n in names if (trials_dir / n).is_dir()]
    if not cands:
        return None
    for p in cands:
        rp = p / "verifier" / "reward.json"
        if rp.is_file():
            try:
                d = json.loads(rp.read_text(encoding="utf-8"))
            except Exception:
                continue
            if d.get("verifier_error") in (0, 0.0) and d.get("reward") is not None:
                return p
    return cands[0]
MODELS = ["qwen3.8-max-0902", "gpt-5.6-sol", "claude-opus-4-8"]
TRAJ_FILES = ["trial.log", "claude-code.txt", "trajectory.json"]


def archive_run(run: str, src: pathlib.Path):
    out = DST / run
    if out.exists():
        shutil.rmtree(out)
    (out / "output").mkdir(parents=True, exist_ok=True)
    (out / "轨迹").mkdir(parents=True, exist_ok=True)

    arts = src / "artifacts" / "app" / "output"
    copied = 0
    if arts.is_dir():
        for p in sorted(arts.iterdir()):
            if p.is_file():
                shutil.copy2(p, out / "output" / p.name)
                copied += 1

    for cand in (src / "verifier" / "reward.json", src / "reward.json"):
        if cand.is_file():
            shutil.copy2(cand, out / "reward.json")
            break
    for cand in (src / "verifier" / "reward-details.json", src / "reward-details.json"):
        if cand.is_file():
            shutil.copy2(cand, out / "reward-details.json")
            break

    for root in (src, src / "agent"):
        if not root.is_dir():
            continue
        for p in sorted(root.iterdir()):
            if p.is_file() and p.name in TRAJ_FILES:
                shutil.copy2(p, out / "轨迹" / p.name)
    for name in ("claude-code.txt", "trajectory.json"):
        if not (out / "轨迹" / name).exists():
            hit = sorted(src.rglob(name))
            if hit:
                shutil.copy2(hit[0], out / "轨迹" / name)

    if run == "oracle" and not (out / "轨迹" / "claude-code.txt").exists():
        (out / "轨迹" / "说明.txt").write_text(
            "oracle 为 harbor 内置参考解执行体，其 agent 阶段不产生 claude-code 轨迹文件，"
            "故本目录无 claude-code.txt / trajectory.json，仅保留 trial.log；"
            "口径与 FIN3-WKN-149/151/152 一致。\n", encoding="utf-8", newline="\n")

    reward = None
    rp = out / "reward.json"
    if rp.is_file():
        try:
            reward = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:
            reward = None
    print(f"[{run}] 交付物 {copied} 项；reward={reward}")
    return reward


def measure_band(mean):
    """A1 ∈[0.6,0.7) / A2 ∈[0.5,0.6) / A3 <0.5；≥0.7 为破档（不落档，须补难度）。"""
    if mean is None:
        return None
    if mean >= 0.7:
        return None
    if mean >= 0.6:
        return "A1"
    if mean >= 0.5:
        return "A2"
    return "A3"


def build_summary(rewards):
    runs = []
    for model, val in rewards.items():
        if not val:
            continue
        runs.append({"model": model, "trial": f"{model}-153" if model != "oracle" else "oracle-153",
                     "reward": val.get("reward"),
                     "criteria_counted": val.get("criteria_counted"),
                     "verifier_error": val.get("verifier_error")})
    oracle = next((r["reward"] for r in runs if r["model"] == "oracle"), None)
    cand = [(r["model"], r["reward"]) for r in runs
            if r["model"] in MODELS and r.get("verifier_error") in (0, 0.0)
            and r.get("reward") is not None]
    partial = round(sum(v for _m, v in cand) / len(cand), 6) if len(cand) >= 2 else None
    mean = (round(sum(v for _m, v in cand) / len(cand), 6)
            if len(cand) == len(MODELS) else None)
    missing = [m for m in MODELS if m not in {r["model"] for r in runs}]
    band = measure_band(mean)
    gate = None
    if oracle is not None and mean is not None:
        gate = bool(oracle > 0.85 and mean < 0.70)
    blocker = None
    if mean is None:
        if "claude-opus-4-8" in missing:
            blocker = ("G5 未完成：claude-opus-4-8 端点不可用（甲方 2026-10-12 指示暂不跑），"
                       f"已取得 {len(cand)}/{len(MODELS)} 个执行体"
                       f"（两模型参考均值 {partial}）；三模型均分与难度定档待补跑后计算")
        else:
            blocker = (f"G5 未完成：尚缺 {missing}" if missing else
                       "G5 执行体存在 verifier_error≠0，须重跑后再定档")
    summary = {
        "task_id": TASK,
        "task_version": "1.0.0",
        "round": "v1.0.0",
        "runs": runs,
        "invalid_runs": [r for r in runs if r.get("verifier_error") not in (0, 0.0, None)],
        "oracle_reward": oracle,
        "three_model_mean": mean,
        "partial_two_model_mean": partial,
        "partial_models": [m for m, _v in cand],
        "three_model_gate": "<0.70",
        "three_model_complete": mean is not None,
        "measured_band": band,
        "declared_difficulty": "A2",
        "declared_complexity": "C4",
        "gate_pass": gate,
        "blocker": blocker,
    }
    (DST / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("[summary]", json.dumps({k: summary[k] for k in
                                   ("oracle_reward", "three_model_mean", "measured_band",
                                    "gate_pass", "blocker")}, ensure_ascii=False))


def main():
    DST.mkdir(parents=True, exist_ok=True)
    rewards = {}
    if "--summary" in sys.argv:
        for run, _dir, _names in RUNS:
            rp = DST / run / "reward.json"
            rewards[run] = json.loads(rp.read_text(encoding="utf-8")) if rp.is_file() else None
    else:
        for run, trials_dir, names in RUNS:
            src = pick_trial(trials_dir, names)
            if src is not None:
                print(f"[pick] {run} <- {src.name}")
                rewards[run] = archive_run(run, src)
            else:
                print(f"[skip] {run}: 无可用 trial（{trials_dir}）")
                rp = DST / run / "reward.json"
                rewards[run] = json.loads(rp.read_text(encoding="utf-8")) if rp.is_file() else None
    build_summary(rewards)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
