"""把 runner 的原始 run 目录整理成交付包里的 jobs/<job_id>/{agent,verifier} 记录。

118 号返修原因：上一版交付包里 8 个候选 job 的 agent/run.json 写着
``artifacts_present=false``、verifier/result.json 写着 ``raw_log_present=false``，
原始 agent log/trajectory 与 test log/checks 没有随包交付，job 也无法与当前
Task（task_id + task_version + task_hash）绑定。

本脚本做的是**从原始跑分现场重建 job 目录**（而不是给旧 job 补文件）：

输入 ``<runs>/<task_id>/<run_id>/<label>/``（目录名即 job_id）下的
    agent.log / prompt.system.txt / prompt.task.txt / task_identity.json
    result.json / checks.json / test.log / stderr.log
原样拷进 ``jobs/<run_id>/{agent,verifier}/``，并写出：
    job.json       —— 汇总字段（verdict / report_status / reason / turns / …）
    agent/run.json —— 轨迹存在性声明（artifacts_present=true）
    binding.json   —— Task 身份三元组 + 镜像 digest + 每个证据文件的 sha256

只有在 run 时 ``task_identity.json`` 记录的 ``task_hash`` 与当前题包重算结果
完全一致的 run 才会被收录——证据只绑定到它实际跑过的那份 Task。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

AGENT_FILES = ("agent.log", "prompt.system.txt", "prompt.task.txt", "task_identity.json")
VERIFIER_FILES = ("result.json", "checks.json", "test.log", "stderr.log")

SKIP_DIRS = {"jobs", "runs", "work", "results", "__pycache__",
             ".pytest_cache", ".mypy_cache", ".git"}

# run_label -> (model_key, role)
LABEL_ROLES = {
    "qwen3.8-max-0902": ("QWEN", "candidate"),
    "opus-5": ("OPUS", "candidate"),
    "glm-5.3": ("GLM", "candidate"),
    "kimi-k3": ("KIMI", "candidate"),
    "no-change": ("NOP", "no-change"),
    "golden": ("ORACLE", "golden"),
    "oracle": ("ORACLE", "golden"),
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_task_hash(task_dir: Path) -> str:
    """与 runner.py / bind_and_enrich_jobs.py 完全一致的 task_hash 口径。"""
    digest = hashlib.sha256()
    for path in sorted(p for p in task_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(task_dir)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        digest.update(rel.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(payload).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def count_turns(agent_log: Path) -> int | None:
    if not agent_log.is_file():
        return None
    text = agent_log.read_text(encoding="utf-8", errors="replace")
    turns = [int(m.group(1)) for m in re.finditer(r"^--- turn (\d+) ", text, re.M)]
    return max(turns) if turns else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", type=Path, required=True,
                    help="题包目录（含 jobs/），例如 harbor-windows/wfflab__wchunk-216")
    ap.add_argument("--runs", type=Path, required=True,
                    help="runner 的 runs/<task_id> 目录")
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--match", default=None,
                    help="只收录 run_id 匹配该正则的 run（例如 ^20261010T12）")
    ap.add_argument("--archive-existing", action="store_true",
                    help="把 jobs/ 下原有的 job（无原始证据的旧记录）移到 jobs/_superseded/")
    args = ap.parse_args()

    package = args.package.resolve()
    jobs_dir = package / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    if not args.runs.is_dir():
        raise SystemExit(f"runs 目录不存在: {args.runs}")

    current_hash = compute_task_hash(package)
    pattern = re.compile(args.match) if args.match else None
    report: list[dict] = []

    if args.archive_existing:
        for job in sorted(p for p in jobs_dir.iterdir()
                          if p.is_dir() and not p.name.startswith("_")):
            target = jobs_dir / "_superseded" / job.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(job), str(target))
            report.append({"job_id": job.name, "status": "archived-superseded",
                           "archived_to": str(target)})

    for run_dir in sorted(p for p in args.runs.iterdir() if p.is_dir()):
        run_id = run_dir.name
        entry: dict = {"job_id": run_id, "task_hash_current": current_hash}
        if pattern and not pattern.search(run_id):
            continue

        label_dirs = sorted(p.parent for p in run_dir.rglob("result.json"))
        if not label_dirs:
            entry["status"] = "no-result-json"
            report.append(entry)
            continue
        label_dir = label_dirs[0]
        label = label_dir.name
        entry["raw_label_dir"] = str(label_dir)

        identity_path = label_dir / "task_identity.json"
        if not identity_path.is_file():
            entry["status"] = "no-task-identity"
            report.append(entry)
            continue
        identity = read_json(identity_path)
        recorded_hash = identity.get("task_hash")
        entry["task_hash_recorded"] = recorded_hash
        if recorded_hash != current_hash:
            entry["status"] = "hash-mismatch"
            report.append(entry)
            continue

        result = read_json(label_dir / "result.json")
        mode = result.get("mode") or ("no-change" if "no-change" in run_id else "candidate")
        model_key, role = LABEL_ROLES.get(label, (label.upper(), mode))
        report_status = (result.get("run_validity")
                         or (result.get("test") or {}).get("report", {}).get("status")
                         or "UNKNOWN")
        finished_at = ((result.get("runner") or {}).get("finished_at")
                       or datetime.now(timezone.utc).isoformat())

        job_dir = jobs_dir / run_id
        if job_dir.exists():
            shutil.rmtree(job_dir)

        copied: list[dict] = []

        def copy(src: Path, dst: Path, tag: str) -> None:
            if not src.is_file():
                return
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append({"path": tag, "bytes": dst.stat().st_size,
                           "sha256": sha256_file(dst)})

        for name in AGENT_FILES:
            copy(label_dir / name, job_dir / "agent" / name, f"agent/{name}")
        for name in VERIFIER_FILES:
            copy(label_dir / name, job_dir / "verifier" / name, f"verifier/{name}")

        turns = count_turns(label_dir / "agent.log")
        agent_status = "completed" if (label_dir / "agent.log").is_file() else "no-agent-log"

        job_doc = {
            "task_id": identity.get("task_id"),
            "task_version": identity.get("task_version"),
            "task_hash": recorded_hash,
            "job_id": run_id,
            "run_id": run_id,
            "run_label": label,
            "mode": mode,
            "role": role,
            "model_key": model_key,
            "verdict": result.get("verdict"),
            "report_status": report_status,
            "reason": result.get("reason"),
            "duration_seconds": result.get("duration_seconds"),
            "agent_status": agent_status,
            "turns": turns,
            "test_log_sha256": sha256_file(label_dir / "test.log") if (label_dir / "test.log").is_file() else None,
            "mtime_utc": finished_at,
            "excluded": False,
            "exclusion": None,
            "scoring_policy": "scored",
            "artifact_binding": "job/binding.json",
            "evidence_files": [c["path"] for c in copied],
            "source": {
                "runner": "deliverables/2026-10-04_outside-harbor-win/runner/runner.py",
                "run_dir": str(label_dir),
                "run_id": run_id,
                "label": label,
                "image_digest": identity.get("docker_image_digest"),
            },
        }
        write_json(job_dir / "job.json", job_doc)

        agent_doc = {
            "job_id": run_id,
            "task_id": identity.get("task_id"),
            "task_version": identity.get("task_version"),
            "role": role,
            "mode": mode,
            "model_key": model_key,
            "model_label": label,
            "agent_status": agent_status,
            "turns": turns,
            "duration_seconds": result.get("duration_seconds"),
            "excluded": False,
            "exclusion": None,
            "artifacts_present": (label_dir / "agent.log").is_file(),
            "artifacts_note": (
                "原始逐轮证据随包交付：agent/agent.log 是完整的 提示词→模型响应→工具调用→工具结果 "
                "轨迹；agent/prompt.system.txt 与 agent/prompt.task.txt 是本次 run 实际使用的提示词；"
                "agent/task_identity.json 固定了本次 run 的 task_id/task_version/task_hash 与镜像 digest。"
            ),
            "raw_label_dir": str(label_dir),
            "task_identity": identity,
        }
        write_json(job_dir / "agent" / "run.json", agent_doc)

        # verifier/result.json 保留容器原始产出，只补上轨迹存在性说明。
        result_doc = read_json(label_dir / "result.json")
        result_doc["raw_log_present"] = (label_dir / "test.log").is_file()
        result_doc["raw_log_note"] = (
            "原始 verifier/test.log（容器内 pytest 完整输出）、verifier/checks.json（逐项 "
            "test_id→status→detail）与 verifier/stderr.log 已随包交付，sha256 见 job/binding.json。"
        )
        result_doc["raw_label_dir"] = str(label_dir)
        write_json(job_dir / "verifier" / "result.json", result_doc)
        copied = [c for c in copied if c["path"] != "verifier/result.json"]
        copied.append({"path": "verifier/result.json",
                       "bytes": (job_dir / "verifier" / "result.json").stat().st_size,
                       "sha256": sha256_file(job_dir / "verifier" / "result.json")})

        binding = {
            "job_id": run_id,
            "task_id": identity.get("task_id"),
            "task_version": identity.get("task_version"),
            "task_hash": recorded_hash,
            "task_hash_algorithm": identity.get("task_hash_algorithm"),
            "docker_image": identity.get("docker_image"),
            "docker_image_digest": identity.get("docker_image_digest"),
            "run_started_at": identity.get("captured_at"),
            "run_finished_at": finished_at,
            "raw_label_dir": str(label_dir),
            "verdict": result.get("verdict"),
            "report_status": report_status,
            "evidence": sorted(copied, key=lambda x: x["path"]),
        }
        write_json(job_dir / "binding.json", binding)

        entry["status"] = "created"
        entry["evidence_files"] = len(binding["evidence"])
        entry["verdict"] = result.get("verdict")
        entry["report_status"] = report_status
        report.append(entry)
        print(f"created  {run_id}  verdict={result.get('verdict')} status={report_status} "
              f"turns={turns} files={len(binding['evidence'])}", flush=True)

    write_json(args.report, {
        "package": str(package),
        "runs": str(args.runs),
        "task_hash_current": current_hash,
        "jobs": report,
        "summary": {
            "created": sum(1 for r in report if r["status"] == "created"),
            "archived-superseded": sum(1 for r in report if r["status"] == "archived-superseded"),
            "hash-mismatch": sum(1 for r in report if r["status"] == "hash-mismatch"),
            "no-task-identity": sum(1 for r in report if r["status"] == "no-task-identity"),
            "no-result-json": sum(1 for r in report if r["status"] == "no-result-json"),
        },
    })
    for r in report:
        if r["status"] != "created":
            print(f"{r['status']:<20} {r['job_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
