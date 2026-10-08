"""Fill in real `turns` for model runs and declare the absence of an agent
trajectory for control rounds (oracle / nop / golden / no-change).

Control rounds never execute the candidate agent, so they legitimately have no
trajectory, turn inputs, or tool calls. Recording that explicitly keeps each
job's agent/ self-describing instead of looking like a missing artefact.
"""
from __future__ import annotations

import json
from pathlib import Path

TASK = "wfflab__wreparse-217"
PKG = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows") / TASK
JOBS = PKG / "jobs"

q = json.loads((JOBS / "_index" / "qualification_summary.json").read_text(encoding="utf-8-sig"))

# run_id -> real turn count (model runs only)
turns: dict[str, int] = {}
for model in q["models"].values():
    for run in list(model.get("selected") or []) + list(model.get("excluded_agent_failures") or []):
        if run.get("turns") is not None:
            turns[run["run_id"]] = run["turns"]

CONTROL_NOTE = (
    "本 job 是控制轮次（{mode}），不运行被测 agent，因此没有 Agent 轨迹、轮次输入输出或工具调用。"
    "判分侧产物见 verifier/：testcase 结果（{cases}）、正式分数（result.json）、日志与运行（{logs}）。"
)

patched_turns = declared = 0
for job in sorted(p for p in JOBS.iterdir() if p.is_dir()):
    job_json = job / "job.json"
    if not job_json.is_file():
        continue
    doc = json.loads(job_json.read_text(encoding="utf-8-sig"))
    mode = str(doc.get("mode"))
    is_model_run = mode == "candidate"

    if is_model_run and job.name in turns:
        if doc.get("turns") != turns[job.name]:
            doc["turns"] = turns[job.name]
            job_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            patched_turns += 1

    agent_dir = job / "agent"
    agent_dir.mkdir(exist_ok=True)
    run_json = agent_dir / "run.json"
    if run_json.is_file():
        run_doc = json.loads(run_json.read_text(encoding="utf-8-sig"))
        if is_model_run and job.name in turns:
            run_doc["turns"] = turns[job.name]
        if not is_model_run:
            run_doc.setdefault("trajectory_present", False)
            run_doc["trajectory_note"] = (
                f"控制轮次（{mode}）：本 job 不运行被测 agent，故 agent/ 下没有轨迹、轮次或工具调用。"
            )
        run_json.write_text(json.dumps(run_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    has_traj = any((agent_dir / n).is_file() for n in ("agent.log", "oracle.txt", "trajectory.jsonl"))
    if not is_model_run and not has_traj:
        vfiles = sorted(f.name for f in (job / "verifier").iterdir()) if (job / "verifier").is_dir() else []
        cases = ", ".join([f for f in vfiles if f in ("checks.json", "report.json")]) or "无"
        logs = ", ".join([f for f in vfiles if f in ("test.log", "stderr.log", "test-stdout.txt", "trial.log")]) or "无"
        (agent_dir / "README.md").write_text(
            "# agent/ 说明\n\n" + CONTROL_NOTE.format(mode=mode, cases=cases, logs=logs) + "\n",
            encoding="utf-8")
        declared += 1

print(f"turns 回填: {patched_turns} 个 job")
print(f"控制轮次无轨迹声明: {declared} 个 job")

# 复核
missing = []
for job in sorted(p for p in JOBS.iterdir() if p.is_dir()):
    if not (job / "job.json").is_file():
        continue
    doc = json.loads((job / "job.json").read_text(encoding="utf-8-sig"))
    if doc.get("mode") == "candidate" and doc.get("turns") is None:
        missing.append(job.name)
    if doc.get("mode") != "candidate":
        ad = job / "agent"
        if not (ad / "README.md").is_file() and not any((ad / n).is_file() for n in ("oracle.txt",)):
            missing.append(job.name + " (无声明)")
print("剩余缺口:", missing if missing else "无")
