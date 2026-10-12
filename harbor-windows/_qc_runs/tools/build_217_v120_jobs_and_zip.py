"""为 217 v1.2.0 生成控制组 job 记录（Oracle ×3 / NOP ×3）并打包交付 zip。

诚实性约定：本轮记录由**本机直跑 Windows PowerShell 5.1** 产生，不是 Windows
容器内的 Harbor 运行。记录里的 source.runner / harness 字段如实写明这一点，
绝不伪装成 `harbor run --env windows_qc_env:WindowsQCEnvironment` 的产物。
容器口径的复跑留待 Docker 恢复 Windows Containers 模式后执行。

目录布局与既有 job 保持一致：
  jobs/<run_id>/job.json
  jobs/<run_id>/agent/{run.json, oracle.txt|nop.txt}
  jobs/<run_id>/verifier/{report.json,result.json,reward.txt,test-stdout.txt}
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK_ID = "wfflab__wreparse-217"
SRC = WS / "harbor-windows" / TASK_ID
JOBS = SRC / "jobs"
BACKUP = WS / "_qc_runs" / "backup-217-before-deepen-v12"
CANDIDATE = BACKUP / "WReparse-candidate"
VERSION = "1.2.0"
CST = timezone(timedelta(hours=8))
PWSH = "powershell.exe"

SKIP_DIRS = {"extras", "__pycache__", ".pytest_cache", ".git", ".mypy_cache"}
SKIP_FILES = {".DS_Store"}


def tree_hash(task_dir: Path) -> str:
    """与 _index 材料一致：排除 jobs/ 与 platform_import.json。"""
    digest = hashlib.sha256()
    files = sorted(
        p for p in task_dir.rglob("*")
        if p.is_file() and "jobs" not in p.relative_to(task_dir).parts
        and p.relative_to(task_dir).as_posix() != "platform_import.json"
    )
    for path in files:
        rel = path.relative_to(task_dir).as_posix()
        digest.update(rel.encode("utf-8") + b"\n")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()


def run_ps(script: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run([PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def restore_candidate() -> None:
    target = SRC / "environment/workspace/WReparse"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(CANDIDATE, target)


def run_job(mode: str, index: int, stamp: str) -> dict:
    """执行一轮并写出 job 目录。mode: golden -> oracle payload; no-change -> candidate."""
    is_golden = mode == "golden"
    run_id = f"{stamp}-{'golden-oracle' if is_golden else 'no-change-nop'}-{index:02d}"
    agent_dir = JOBS / run_id / "agent"
    verifier_dir = JOBS / run_id / "verifier"
    agent_dir.mkdir(parents=True, exist_ok=True)
    verifier_dir.mkdir(parents=True, exist_ok=True)

    started = datetime.now(CST)
    agent_out = ""
    if is_golden:
        code, agent_out = run_ps(SRC / "solution/solve.ps1", "-TaskRoot", str(SRC))
        if code != 0:
            return {"run_id": run_id, "error": f"solve.ps1 exit={code}: {agent_out.strip()}"}
        (agent_dir / "oracle.txt").write_text(agent_out, encoding="utf-8")
    else:
        restore_candidate()
        agent_out = "no-change: candidate workspace left untouched"
        (agent_dir / "nop.txt").write_text(agent_out + "\n", encoding="utf-8")

    run_ps(SRC / "tests/prepare.ps1", "-TaskRoot", str(SRC))
    test_exit, test_out = run_ps(SRC / "tests/test.ps1", "-TaskRoot", str(SRC))
    (verifier_dir / "test-stdout.txt").write_text(test_out, encoding="utf-8")

    result_path = SRC / "results/result.json"
    checks_path = SRC / "results/checks.json"
    if not result_path.is_file():
        return {"run_id": run_id, "error": "results/result.json missing"}
    doc = json.loads(result_path.read_text(encoding="utf-8-sig"))
    checks = json.loads(checks_path.read_text(encoding="utf-8-sig"))

    duration = round((datetime.now(CST) - started).total_seconds(), 1)
    mtime = datetime.now(timezone.utc).isoformat()
    test_log_sha = hashlib.sha256(checks_path.read_bytes()).hexdigest()
    verdict = int(doc.get("formal_score") or 0)
    status = str(doc.get("run_validity"))
    reason = str(doc.get("reason"))

    shutil.copyfile(result_path, verifier_dir / "report.json")
    (verifier_dir / "reward.txt").write_text(str(verdict), encoding="utf-8", newline="")

    # cases 带 f2p-/p2p- 前缀，与既有 verifier/result.json 一致
    declared = json.loads((SRC / "tests/required_testcases.json").read_text(encoding="utf-8-sig"))
    status_by_bare = {str(c["test_id"]): str(c["status"]) for c in checks["checks"]}
    cases = [{"id": str(d["id"]), "group": str(d["group"]),
              "status": status_by_bare.get(str(d["id"])[4:], "MISSING")} for d in declared]

    verifier_result = {
        "job_id": run_id, "task_id": TASK_ID, "task_version": VERSION,
        "mode": mode, "role": "golden" if is_golden else "no-change",
        "model_key": "ORACLE" if is_golden else "NOP",
        "verdict": verdict, "report_status": status, "reason": reason,
        "test_log_sha256": test_log_sha, "duration_seconds": duration, "mtime_utc": mtime,
        "scored": True, "scoring_policy": "scored", "raw_log_present": True,
        "raw_log_note": ("verifier/report.json (aggregate-v1), reward.txt and test-stdout.txt are the "
                         "originals produced on this host by Windows PowerShell 5.1."),
        "cases": cases,
    }
    (verifier_dir / "result.json").write_text(
        json.dumps(verifier_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    job = {
        "task_id": TASK_ID, "task_version": VERSION, "job_id": run_id, "run_id": run_id,
        "run_label": "oracle" if is_golden else "nop",
        "mode": mode, "role": "golden" if is_golden else "no-change",
        "model_key": "ORACLE" if is_golden else "NOP",
        "verdict": verdict, "report_status": status, "reason": reason,
        "duration_seconds": duration, "agent_status": "completed", "turns": None,
        "test_log_sha256": test_log_sha, "mtime_utc": mtime,
        "excluded": False, "exclusion": None, "scoring_policy": "scored",
        "harness": "local-direct",
        "source": {
            "runner": "local-direct (Windows PowerShell 5.1 on the host)",
            "command": (f"{PWSH} -NoProfile -ExecutionPolicy Bypass -File "
                        f"tests\\test.ps1 -TaskRoot {SRC}"),
            "cli_log": None,
            "trial": None,
            "note": ("本记录由本机直跑产生，不是 Windows 容器内的 Harbor 运行。"
                     "容器口径复跑（harbor run --env windows_qc_env:WindowsQCEnvironment）"
                     "待本机 Docker 恢复 Windows Containers 模式后执行。"),
        },
    }
    (JOBS / run_id / "job.json").write_text(
        json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    agent_run = {
        "job_id": run_id, "task_id": TASK_ID, "task_version": VERSION,
        "role": "golden" if is_golden else "no-change", "mode": mode,
        "model_key": "ORACLE" if is_golden else "NOP",
        "model_label": "oracle" if is_golden else "no-change",
        "agent_status": "completed", "turns": None, "duration_seconds": duration,
        "excluded": False, "exclusion": None, "artifacts_present": True,
        "artifacts_note": ("agent stdout kept as agent/oracle.txt" if is_golden
                           else "no-change control: the candidate workspace was left untouched"),
        "trajectory_present": False,
        "trajectory_note": ("控制轮次：本 job 不运行被测 agent，故 agent/ 下没有轨迹、轮次或工具调用。"),
    }
    (agent_dir / "run.json").write_text(
        json.dumps(agent_run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {"run_id": run_id, "verdict": verdict, "status": status,
            "total": doc.get("total"), "passed": doc.get("passed"),
            "failed": doc.get("failed"), "invalid": doc.get("invalid"),
            "duration": duration, "test_exit": test_exit}


def main() -> int:
    if not CANDIDATE.is_dir():
        print(f"候选备份不存在: {CANDIDATE}")
        return 2

    stamp = datetime.now(CST).strftime("%Y%m%dT%H%M%S")
    rounds = []
    for mode in ("golden", "no-change"):
        for i in range(1, 4):
            r = run_job(mode, i, stamp)
            rounds.append(r)
            if "error" in r:
                print(f"  {mode:10s} #{i}: ERROR {r['error']}")
            else:
                print(f"  {mode:10s} #{i}: {r['run_id']}  validity={r['status']:7s} "
                      f"passed={r['passed']:2d}/{r['total']} score={r['verdict']}")

    restore_candidate()

    problems = []
    for r in rounds:
        if "error" in r:
            problems.append(r["error"])
    if problems:
        print("\n失败：")
        for p in problems:
            print(f"  - {p}")
        return 1

    # -------------------------------------------------------------- 打包 zip
    new_hash = tree_hash(SRC)
    import tomllib
    cfg = tomllib.loads((SRC / "task.toml").read_text(encoding="utf-8"))
    import_json = {
        "instance_id": TASK_ID,
        "task_version": cfg["task"]["version"],
        "task_hash": new_hash,
        "docker_image": "outside-harbor/wfflab__wreparse-217:1.0",
        "image_digest": "sha256:37fdf8e192c68dcc7b88c6a529e49f13141fb8fbccbe8fbad908733f74db68f0",
        "instruction_file": f"{TASK_ID}/instruction.md",
        "assets_path": TASK_ID,
        "harness": ("standalone tests/test.ps1 + run_tests.ps1 + aggregate_results.ps1"
                    "（Harbor schema 1.3；Windows 容器 .bat 入口）"),
        "tags": ["coding", "windows", "windows-bench"],
        "primary_direction": "文件系统与路径",
        "difficulty": cfg["metadata"]["difficulty"],
        "_note": ("本文件仅用于平台导入，不等于标准 Harbor Task；正式题本体以 "
                  f"outside_harbor-assets/{TASK_ID}/ 中通过冻结 Schema 校验的内容为准。"
                  "两者引用同一身份三元组。"),
    }

    out_dir = WS / "deliverables" / "2026-10-09_wreparse217-加深L4" / "package"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{TASK_ID}-v{VERSION}-delivery.zip"

    items: list[tuple[Path, str]] = []
    import os
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
            items.append((current / f, f"outside_harbor-assets/{TASK_ID}/{(rel / f).as_posix()}"))

    # 本轮 oracle 的 verifier 产物作为官方 verifier/
    oracle_jobs = sorted(r["run_id"] for r in rounds if r["run_id"].endswith("-01") and "golden" in r["run_id"])
    if oracle_jobs:
        gdir = JOBS / oracle_jobs[0] / "verifier"
        for f in sorted(gdir.iterdir()):
            if f.is_file():
                items.append((f, f"outside_harbor-assets/{TASK_ID}/verifier/{f.name}"))

    for f in sorted((SRC / "jobs").rglob("*")):
        if f.is_file():
            items.append((f, f"jobs/{f.relative_to(SRC / 'jobs').as_posix()}"))

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"outside_harbor/{TASK_ID}.json",
                    json.dumps(import_json, ensure_ascii=False, indent=2) + "\n")
        for path, arc in items:
            zf.write(path, arc)

    names = zipfile.ZipFile(zip_path).namelist()
    print()
    print(f"task_hash = {new_hash}")
    print(f"zip       = {zip_path}")
    print(f"大小      = {zip_path.stat().st_size} B   条目 {len(names)}")
    print(f"顶层      = {sorted({n.split('/')[0] for n in names})}")
    print(f"assets 内 = {sum(1 for n in names if n.startswith(f'outside_harbor-assets/{TASK_ID}/'))} 条")
    print(f"jobs 内   = {sum(1 for n in names if n.startswith('jobs/'))} 条")
    print(f"verifier/ = {sorted(n.split('/')[-1] for n in names if f'assets/{TASK_ID}/verifier/' in n)}")
    print(f"zip sha256= {hashlib.sha256(zip_path.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
