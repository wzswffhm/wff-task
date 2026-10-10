"""Bind每份已交付的 job 到当前 Task 身份，并回填原始跑分证据。

背景（118 号返修原因）：上一版交付包里 8 个候选 job 的
``agent/run.json`` 写着 ``artifacts_present=false``、``verifier/result.json``
写着 ``raw_log_present=false``——原始 agent log/trajectory 与 test log/checks
根本没有随包交付，job 也无法与当前 Task（task_id + task_version + task_hash）
绑定，导致质检无法审计。

本脚本做两件事，二者都可被接收方独立复算：

1. **回填原始证据**：从本地 runner 的 run 目录
   （``<runs>/<task_id>/<run_id>/<label>/``，目录名即 job 名）把
   ``agent.log`` / ``prompt.system.txt`` / ``prompt.task.txt`` /
   ``task_identity.json`` 与 ``checks.json`` / ``test.log`` / ``stderr.log`` /
   ``result.json`` 拷进对应 job，并逐项记录 sha256。
2. **绑定 Task 身份**：重算题包 ``task_hash``，与 run 时记录的
   ``task_identity.json`` 比对；生成 job 级 ``binding.json`` 记录
   task_id / task_version / task_hash / 镜像 digest / 每个证据文件的 sha256。

已被 run 时 ``task_identity.json`` 记录的 hash 与当前题包不一致的 job 会被标为
``hash-mismatch`` 并**拒绝回填**——证据只能绑定到它实际跑过的那份 Task。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

EVIDENCE = ("checks.json", "test.log", "stderr.log", "result.json")
AGENT_FILES = ("agent.log", "prompt.system.txt", "prompt.task.txt", "task_identity.json")

SKIP_DIRS = {"jobs", "runs", "work", "results", "__pycache__",
             ".pytest_cache", ".mypy_cache", ".git"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_task_hash(task_dir: Path) -> str:
    """与 runner.py 完全一致的 task_hash 口径。"""
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", type=Path, required=True,
                    help="题包目录（含 jobs/），例如 harbor-windows/wfflab__wchunk-216")
    ap.add_argument("--runs", type=Path, required=True,
                    help="runner 的 runs/<task_id> 目录")
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--archive-unmatched", action="store_true",
                    help="把在 runs 里找不到原始证据的 job 移到 jobs/_superseded/")
    args = ap.parse_args()

    package = args.package.resolve()
    jobs_dir = package / "jobs"
    if not jobs_dir.is_dir():
        raise SystemExit(f"jobs 目录不存在: {jobs_dir}")
    if not args.runs.is_dir():
        raise SystemExit(f"runs 目录不存在: {args.runs}")

    current_hash = compute_task_hash(package)
    report: list[dict] = []

    for job in sorted(p for p in jobs_dir.iterdir() if p.is_dir() and not p.name.startswith("_")):
        run_dir = args.runs / job.name
        entry: dict = {"job_id": job.name, "task_hash_current": current_hash}

        if not run_dir.is_dir():
            entry["status"] = "no-raw-evidence"
            report.append(entry)
            if args.archive_unmatched:
                target = jobs_dir / "_superseded" / job.name
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    shutil.rmtree(target)
                shutil.move(str(job), str(target))
                entry["archived_to"] = str(target)
            continue

        label_dirs = sorted(p.parent for p in run_dir.rglob("test.log"))
        if not label_dirs:
            entry["status"] = "no-raw-evidence"
            report.append(entry)
            continue
        label_dir = label_dirs[0]
        entry["raw_label_dir"] = str(label_dir)

        identity_src = label_dir / "task_identity.json"
        if not identity_src.is_file():
            entry["status"] = "no-task-identity"
            report.append(entry)
            continue
        identity = read_json(identity_src)
        recorded_hash = identity.get("task_hash")
        entry["task_hash_recorded"] = recorded_hash
        if recorded_hash != current_hash:
            entry["status"] = "hash-mismatch"
            report.append(entry)
            continue

        copied: list[dict] = []

        def copy(src: Path, dst: Path, tag: str) -> None:
            if not src.is_file():
                return
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append({"path": tag, "bytes": dst.stat().st_size,
                           "sha256": sha256_file(dst)})

        for name in AGENT_FILES:
            copy(label_dir / name, job / "agent" / name, f"agent/{name}")
        for name in EVIDENCE:
            copy(label_dir / name, job / "verifier" / name, f"verifier/{name}")

        # 判分日志先校验再采信：job.json 里若有 test_log_sha256，必须与原始文件一致。
        job_json = job / "job.json"
        job_doc = read_json(job_json) if job_json.is_file() else {}
        recorded_log_hash = job_doc.get("test_log_sha256")
        actual_log_hash = sha256_file(label_dir / "test.log")
        entry["test_log_sha256_recorded"] = recorded_log_hash
        entry["test_log_sha256_actual"] = actual_log_hash
        if recorded_log_hash and recorded_log_hash != actual_log_hash:
            entry["status"] = "sha256-mismatch"
            report.append(entry)
            continue

        run_json = job / "agent" / "run.json"
        if run_json.is_file():
            doc = read_json(run_json)
            doc["artifacts_present"] = True
            doc["artifacts_note"] = (
                "原始逐轮证据已随包交付：agent/agent.log（完整提示词→响应→工具调用→结果轨迹）、"
                "agent/prompt.system.txt、agent/prompt.task.txt、agent/task_identity.json、"
                "verifier/{checks.json,test.log,stderr.log,result.json}")
            doc["raw_label_dir"] = str(label_dir)
            doc["task_identity"] = identity
            write_json(run_json, doc)
            copied.append({"path": "agent/run.json", "bytes": run_json.stat().st_size,
                           "sha256": sha256_file(run_json)})

        result_json = job / "verifier" / "result.json"
        if result_json.is_file():
            doc = read_json(result_json)
            doc["raw_log_present"] = True
            doc["raw_log_note"] = (
                "原始 test.log / checks.json / stderr.log 已随包交付，sha256 见 job/binding.json")
            doc["raw_label_dir"] = str(label_dir)
            write_json(result_json, doc)
            copied.append({"path": "verifier/result.json", "bytes": result_json.stat().st_size,
                           "sha256": sha256_file(result_json)})

        binding = {
            "job_id": job.name,
            "task_id": identity.get("task_id"),
            "task_version": identity.get("task_version"),
            "task_hash": recorded_hash,
            "task_hash_algorithm": identity.get("task_hash_algorithm"),
            "docker_image": identity.get("docker_image"),
            "docker_image_digest": identity.get("docker_image_digest"),
            "run_started_at": identity.get("captured_at"),
            "raw_label_dir": str(label_dir),
            "verdict": (read_json(result_json).get("verdict") if result_json.is_file() else None),
            "evidence": sorted(copied, key=lambda x: x["path"]),
        }
        write_json(job / "binding.json", binding)

        if job_json.is_file():
            job_doc["artifact_binding"] = "job/binding.json"
            job_doc["task_hash"] = recorded_hash
            job_doc["evidence_files"] = [c["path"] for c in binding["evidence"]]
            write_json(job_json, job_doc)

        entry["status"] = "bound"
        entry["evidence_files"] = len(binding["evidence"])
        report.append(entry)

    write_json(args.report, {
        "package": str(package),
        "runs": str(args.runs),
        "task_hash_current": current_hash,
        "jobs": report,
        "summary": {
            "bound": sum(1 for r in report if r["status"] == "bound"),
            "no-raw-evidence": sum(1 for r in report if r["status"] == "no-raw-evidence"),
            "hash-mismatch": sum(1 for r in report if r["status"] == "hash-mismatch"),
            "sha256-mismatch": sum(1 for r in report if r["status"] == "sha256-mismatch"),
            "no-task-identity": sum(1 for r in report if r["status"] == "no-task-identity"),
        },
    })
    for r in report:
        print(f"{r['status']:<18} {r['job_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
