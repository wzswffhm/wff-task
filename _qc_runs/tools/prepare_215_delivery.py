"""Bring wfflab__wfmt-215 to the same delivery state as 217:
  1. refresh platform_import.json so its identity matches task.toml
  2. declare the absence of a trajectory on control-round jobs
  3. build the delivery zip in the platform layout
"""
from __future__ import annotations

import hashlib
import json
import os
import tomllib
import zipfile
from pathlib import Path

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = "wfflab__wfmt-215"
SRC = WS / "harbor-windows" / TASK
JOBS = SRC / "jobs"
OUT_DIR = WS / "deliverables" / "2026-10-08_harbor-windows-整改" / "package"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ZIP = OUT_DIR / f"{TASK}-v2.0.0-delivery.zip"
GOLDEN_JOB = "20261008T200943-golden-oracle-01"
SKIP_DIRS = {"extras", "__pycache__", ".pytest_cache", ".git", ".mypy_cache"}
SKIP_FILES = {".DS_Store"}


def tree_hash(task_dir: Path) -> str:
    """题包定义树哈希。

    platform_import.json 记录的就是本值，因此必须从被哈希的集合里排除自身，
    否则哈希永远无法自洽（写入后文件变化 → 哈希失效）。
    """
    digest = hashlib.sha256()
    files = sorted(p for p in task_dir.rglob("*")
                   if p.is_file() and "jobs" not in p.relative_to(task_dir).parts
                   and p.relative_to(task_dir).as_posix() != "platform_import.json")
    for path in files:
        digest.update(path.relative_to(task_dir).as_posix().encode() + b"\n")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode() + b"\n")
    return digest.hexdigest()


# ---------------------------------------------------------------- 1) import json
cfg = tomllib.loads((SRC / "task.toml").read_text(encoding="utf-8"))
old = json.loads((SRC / "platform_import.json").read_text(encoding="utf-8-sig"))
new = {
    "instance_id": TASK,
    "task_version": cfg["task"]["version"],
    "task_hash": tree_hash(SRC),
    "docker_image": "outside-harbor/wfflab__wfmt-215:1.0",
    "image_digest": "sha256:36b792b8c6bbfb03925dba2453f68bc77b6026644d2d687f6a12a39357153007",
    "instruction_file": f"{TASK}/instruction.md",
    "assets_path": TASK,
    "harness": "standalone tests/test.ps1 + run_tests.ps1 + aggregate_results.ps1（Harbor schema 1.3；Windows 容器 .bat 入口）",
    "tags": ["coding", "windows", "windows-bench"],
    "primary_direction": "编码与区域（二进制容器格式）",
    "difficulty": cfg["metadata"]["difficulty"],
    "_note": ("本文件仅用于平台导入，不等于标准 Harbor Task；正式题本体以同目录（"
              f"{TASK}/）中通过冻结 Schema 校验的内容为准。两者引用同一身份三元组。"),
}
(SRC / "platform_import.json").write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8")
print("platform_import.json updated:")
for k in ("task_version", "difficulty", "docker_image", "task_hash"):
    mark = "changed" if old.get(k) != new.get(k) else "same"
    print(f"   {k:<14} {str(old.get(k))[:34]:<36} -> {str(new.get(k))[:34]:<36} [{mark}]")

# ------------------------------------------------------------- 2) control rounds
q = json.loads((JOBS / "_index" / "qualification_summary.json").read_text(encoding="utf-8-sig"))
turns: dict[str, int] = {}
for model in q["models"].values():
    for run in list(model.get("selected") or []) + list(model.get("excluded_agent_failures") or []):
        if run.get("turns") is not None:
            turns[run["run_id"]] = run["turns"]

declared = 0
for job in sorted(p for p in JOBS.iterdir() if p.is_dir()):
    if not (job / "job.json").is_file():
        continue
    doc = json.loads((job / "job.json").read_text(encoding="utf-8-sig"))
    mode = str(doc.get("mode"))
    is_model_run = mode == "candidate"
    agent_dir = job / "agent"
    agent_dir.mkdir(exist_ok=True)
    run_json = agent_dir / "run.json"
    if run_json.is_file():
        rd = json.loads(run_json.read_text(encoding="utf-8-sig"))
        if is_model_run and job.name in turns:
            rd["turns"] = turns[job.name]
        if not is_model_run:
            rd.setdefault("trajectory_present", False)
            rd["trajectory_note"] = f"控制轮次（{mode}）：本 job 不运行被测 agent，故 agent/ 下没有轨迹、轮次或工具调用。"
        run_json.write_text(json.dumps(rd, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    has_traj = any((agent_dir / n).is_file() for n in ("agent.log", "oracle.txt", "trajectory.jsonl"))
    if not is_model_run and not has_traj and not (agent_dir / "README.md").is_file():
        vf = sorted(f.name for f in (job / "verifier").iterdir()) if (job / "verifier").is_dir() else []
        cases = ", ".join(f for f in vf if f in ("checks.json", "report.json")) or "无"
        logs = ", ".join(f for f in vf if f in ("test.log", "stderr.log", "test-stdout.txt", "trial.log")) or "无"
        (agent_dir / "README.md").write_text(
            "# agent/ 说明\n\n"
            f"本 job 是控制轮次（{mode}），不运行被测 agent，因此没有 Agent 轨迹、轮次输入输出或工具调用。"
            f"判分侧产物见 verifier/：testcase 结果（{cases}）、正式分数（result.json）、日志与运行（{logs}）。\n",
            encoding="utf-8")
        declared += 1
print(f"控制轮次声明补齐: {declared} 个 job")

# --------------------------------------------------------------------- 3) zip
items: list[tuple[Path, str]] = []
for dirpath, dirnames, filenames in os.walk(SRC):
    current = Path(dirpath)
    rel = current.relative_to(SRC)
    if rel.parts[:1] == ("jobs",):
        dirnames[:] = []
        continue
    dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
    for f in sorted(filenames):
        if f in SKIP_FILES or f.endswith(".pyc"):
            continue
        items.append((current / f, f"outside_harbor-assets/{TASK}/{(rel / f).as_posix()}"))
gdir = JOBS / GOLDEN_JOB / "verifier"
for f in sorted(gdir.iterdir()) if gdir.is_dir() else []:
    if f.is_file():
        items.append((f, f"outside_harbor-assets/{TASK}/verifier/{f.name}"))
for f in sorted(JOBS.rglob("*")):
    if f.is_file():
        items.append((f, f"jobs/{f.relative_to(JOBS).as_posix()}"))

with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(f"outside_harbor/{TASK}.json", json.dumps(new, ensure_ascii=False, indent=2) + "\n")
    for path, arc in items:
        zf.write(path, arc)

names = zipfile.ZipFile(ZIP).namelist()
print(f"\nzip    : {ZIP.name}  {ZIP.stat().st_size} B  条目 {len(names)}")
print(f"顶层   : {sorted({n.split('/')[0] for n in names})}")
print(f"jobs/  : {sum(1 for n in names if n.startswith('jobs/'))}   job 数: "
      f"{len({n.split('/')[1] for n in names if n.startswith('jobs/') and len(n.split('/')) > 2})}")
print(f"verifier/(task): {sorted(n.split('/')[-1] for n in names if f'assets/{TASK}/verifier/' in n)}")
print(f"extras 泄漏: {any('/extras/' in n for n in names)}")
print(f"sha256 : {hashlib.sha256(ZIP.read_bytes()).hexdigest()}")
