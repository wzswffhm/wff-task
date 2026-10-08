# -*- coding: utf-8 -*-
"""build_jobs.py —— 由资格汇总（model_runs_summary_*.json）生成题包 `jobs/` 目录

平台交付结构要求题包（或 `outside_harbor-assets/`）下有 `jobs/`：

    jobs/
    └── <job-id>/
        ├── job.json          # 该作业的身份 + 结果 + 来源指针
        ├── agent/            # 模型侧（控制组不经过 agent）
        │   └── run.json
        └── verifier/         # 判分侧
            └── result.json

本机 runner 的原始产物在 `<runner>/runs/<task-id>/<run_id>/<label>/`
（`agent.log` / `result.json` / `test.log` / `checks.json`），该目录被
`.gitignore` 忽略、不随仓库同步。因此本脚本以**留存的权威汇总**
（`summarize_model_runs.py` 输出）为唯一事实来源，重建最小可核对的 jobs：

* `agent_status ∈ {completed, max_turns}` 才计入有效轮；`error` / `no_tool_call`
  等上游故障轮**保留并标记 `excluded=true`**（说明为何不计分），不得伪装成 0 分。
* 原始 `agent.log` / `test.log` 未留存时，脚本**不伪造**内容：缺口声明内嵌在
  `agent/run.json` 的 `artifacts_note` 与 `verifier/result.json` 的 `raw_log_note`。
* 默认**不生成** `jobs/README.md`（交付目录不留说明文件）；需要时用 `--with-readme`。

用法：
    python build_jobs.py --task-dir <题包目录> --summary <汇总 json>
    python build_jobs.py --task-dir <题包目录> --summary <汇总 json> \
        --local-verification <目录>   # 额外归档的本机复核证据
    python build_jobs.py ... --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from pathlib import Path

SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9\-_]{12,}"), "疑似 API key（sk-）"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-_.=]{12,}"), "疑似 Bearer token"),
    (re.compile(r"(?i)x-api-key\s*[:=]\s*[A-Za-z0-9\-_]{12,}"), "疑似 x-api-key"),
    (re.compile(r"(?i)(api[_-]?key|secret|token)\"?\s*[:=]\s*\"[A-Za-z0-9\-_]{20,}\""), "疑似凭据赋值"),
]

CONTROL_MODES = {"no-change", "golden"}


def load_summary(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "controls" not in data or "models" not in data:
        raise SystemExit(f"汇总文件结构不符（缺 controls/models）：{path}")
    return data


def collect_jobs(summary: dict) -> list[dict]:
    """把汇总展开成平铺的作业列表（含被剔除的上游故障轮）。"""
    jobs: list[dict] = []

    controls = summary.get("controls") or {}
    for mode in ("no_change", "golden"):
        for run in controls.get(mode) or []:
            jobs.append(
                {
                    "run": run,
                    "model_key": None,
                    "role": "control",
                    "excluded": False,
                    "exclusion": None,
                }
            )

    for key, block in (summary.get("models") or {}).items():
        for run in block.get("selected") or []:
            jobs.append(
                {
                    "run": run,
                    "model_key": key,
                    "role": "candidate",
                    "excluded": False,
                    "exclusion": None,
                }
            )
        for run in block.get("excluded_agent_failures") or []:
            jobs.append(
                {
                    "run": run,
                    "model_key": key,
                    "role": "candidate",
                    "excluded": True,
                    "exclusion": run.get("exclusion") or {},
                }
            )

    seen: dict[str, int] = {}
    for job in jobs:
        rid = job["run"].get("run_id")
        if not rid:
            raise SystemExit("存在缺 run_id 的记录，拒绝生成 jobs")
        seen[rid] = seen.get(rid, 0) + 1
    dup = [k for k, v in seen.items() if v > 1]
    if dup:
        raise SystemExit(f"run_id 重复，无法作为唯一 job-id：{dup}")
    return jobs


def build_job_payload(job: dict, summary: dict, summary_rel: str) -> tuple[dict, dict, dict]:
    run = job["run"]
    excluded = job["excluded"]
    policy = "excluded_upstream_failure" if excluded else "scored"

    job_json = {
        "task_id": run.get("task_id"),
        "task_version": run.get("task_version"),
        "job_id": run.get("run_id"),
        "run_id": run.get("run_id"),
        "run_label": run.get("run_label"),
        "mode": run.get("mode"),
        "role": job["role"],
        "model_key": job["model_key"],
        "verdict": run.get("verdict"),
        "report_status": run.get("report_status"),
        "reason": run.get("reason"),
        "duration_seconds": run.get("duration_seconds"),
        "agent_status": run.get("agent_status"),
        "turns": run.get("turns"),
        "test_log_sha256": run.get("test_log_sha256"),
        "mtime_utc": run.get("mtime_utc"),
        "excluded": excluded,
        "exclusion": job["exclusion"] if excluded else None,
        "scoring_policy": policy,
        "qualification_epoch": summary.get("qualification_epoch"),
        "source": {
            "summary_file": summary_rel,
            "original_result_path": run.get("result_path"),
        },
    }

    if job["role"] == "control":
        agent_note = (
            "控制组（no-change / golden）不经过 agent，直接对未修改或已应用参考解的"
            "工作区执行 Verifier；因此无模型轨迹与轮次。"
        )
    elif excluded:
        agent_note = (
            "上游 provider/网关故障轮：按规范不得计 0 分，已排除出计分集合，"
            "仅保留供质检核对剔除依据。原始 agent 日志未随仓库留存。"
        )
    else:
        agent_note = (
            "有效计分轮。原始 agent 轨迹（agent.log / trajectory）位于 runner 的 "
            "runs/ 目录，该目录未随仓库留存，本文件为重述。"
        )

    agent_json = {
        "job_id": run.get("run_id"),
        "task_id": run.get("task_id"),
        "task_version": run.get("task_version"),
        "role": job["role"],
        "mode": run.get("mode"),
        "model_key": job["model_key"],
        "model_label": run.get("run_label"),
        "agent_status": run.get("agent_status"),
        "turns": run.get("turns"),
        "duration_seconds": run.get("duration_seconds"),
        "excluded": excluded,
        "exclusion": job["exclusion"] if excluded else None,
        "artifacts_present": False,
        "artifacts_note": agent_note,
    }

    verifier_json = {
        "job_id": run.get("run_id"),
        "task_id": run.get("task_id"),
        "task_version": run.get("task_version"),
        "mode": run.get("mode"),
        "role": job["role"],
        "model_key": job["model_key"],
        "verdict": run.get("verdict"),
        "report_status": run.get("report_status"),
        "reason": run.get("reason"),
        "test_log_sha256": run.get("test_log_sha256"),
        "duration_seconds": run.get("duration_seconds"),
        "mtime_utc": run.get("mtime_utc"),
        "scored": not excluded,
        "scoring_policy": policy,
        "raw_log_present": False,
        "raw_log_note": (
            "原始 test.log / checks.json 位于 runner 的 runs/ 目录，未随仓库留存；"
            "此处保留其 sha256 与判定结论，可与汇总文件逐条核对。"
        ),
    }
    return job_json, agent_json, verifier_json


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def scan_secrets(root: Path) -> list[str]:
    hits: list[str] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(f"{p.relative_to(root)} :: {label}")
    return hits


def copy_local_verification(src: Path, dest: Path) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    if src.is_file():
        shutil.copy2(src, dest / src.name)
        copied.append(src.name)
        return copied
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        copied.append(rel.as_posix())
    return copied


def render_readme(
    task_id: str, task_version: str, summary_rel: str, jobs: list[dict], extra: list[str]
) -> str:
    counts: dict[str, int] = {}
    for job in jobs:
        mode = job["run"].get("mode") or "?"
        counts[mode] = counts.get(mode, 0) + 1

    lines = [
        f"# jobs —— `{task_id}` 作业记录（{task_version}）",
        "",
        "本目录是**平台交付结构中的 `jobs/`**：每次跑分作业一个 `<job-id>/`，",
        "内含 `agent/`（模型侧）与 `verifier/`（判分侧）。作业 ID 即本机 runner 的 `run_id`，",
        "与资格汇总逐条对应、可直接核对。",
        "",
        "## 目录结构",
        "",
        "```text",
        "jobs/",
        "├── README.md               # 本文件",
        "├── _index/                 # 索引与权威汇总副本",
        "│   ├── jobs_index.csv",
        "│   └── qualification_summary.json",
        "├── _local_verification/    # （若有）本机判分链路复核证据",
        "└── <job-id>/",
        "    ├── job.json            # 身份 + 结果 + 来源指针",
        "    ├── agent/run.json      # 模型侧读数（控制组不经过 agent）",
        "    └── verifier/result.json# 判定结论 + 原始日志 sha256",
        "```",
        "",
        "## 作业构成",
        "",
        "| mode | 作业数 |",
        "|---|---|",
    ]
    for mode, n in sorted(counts.items()):
        lines.append(f"| `{mode}` | {n} |")

    excluded = [j for j in jobs if j["excluded"]]
    lines += [
        "",
        "## 事实来源与缺口（重要）",
        "",
        f"- 唯一事实来源：`{summary_rel}`（`summarize_model_runs.py` 输出，本目录 `_index/` 存有副本）。",
        "- 原始产物在 runner 的 `runs/<task-id>/<run_id>/<label>/`（`agent.log` / `result.json` / "
        "`test.log` / `checks.json`）。该目录被 `.gitignore` 忽略、未随仓库留存，因此本目录**以留存汇总重建**：",
        "  - `verifier/result.json` 保留判定结论与 `test_log_sha256`，可与汇总逐条核对；",
        "  - `agent/run.json` 保留模型、轮次、终止状态与耗时；原始轨迹**未留存，未做任何伪造**。",
        "- 上游故障轮（`agent_status ∈ {error, no_tool_call}`）**保留但不计分**，"
        "以 `excluded: true` 标记并在 `exclusion` 字段写明原因；这正是资格门禁的剔除依据。",
        f"- 本轮共 {len(excluded)} 个剔除作业。",
        "",
        "## 判定口径",
        "",
        "- 二值判分：required F2P + P2P 全过 → `verdict = 1`，否则 `0`；异常为 INVALID，**不得伪装成 0 分**。",
        "- 控制组：`no-change` 期望 `verdict = 0`（核心 F2P 因目标缺陷失败）；`golden` 期望 `verdict = 1`。",
        "- 计分集合只取 `agent_status ∈ {completed, max_turns}` 的有效轮，且同 epoch、同 `task_version`。",
        "",
        "## 复现指引",
        "",
        "1. 以 `_index/qualification_summary.json` 为权威读数，逐条比对 `<job-id>/job.json` 的 `verdict` 与 `reason`。",
        "2. 需要完整轨迹时，用同一冻结题包与同一 epoch 重跑对应作业（runner `--task` + `--mode`/`--models`），",
        "   新作业的 `run_id` 会不同，不得回填为本目录条目。",
        "3. 本目录**不含** `solution/`、答案、隐藏用例或任何凭据。",
        "",
    ]
    if extra:
        lines += [
            "## 本机复核证据（`_local_verification/`）",
            "",
            "以下文件是题包冻结后在本机（真实 Windows Runtime）跑判分链路得到的**原始产物**，",
            "**不隶属于上面任一作业**：其判定结论是「未打补丁工作区」的对照结论（与 `no-change` 同型），",
            "用于佐证判分链路可运行、逐项 checks 可核对。",
            "",
            *[f"- `{name}`" for name in extra],
            "",
        ]
    else:
        lines += [
            "## 本机复核证据",
            "",
            "本次未随附 `_local_verification/`（该轮的本地校准原始日志未留存）；",
            "本地校准与对照结论见交付侧的运行报告（`deliverables/` 下对应批次的报告文件）。",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="由资格汇总生成题包 jobs/ 目录")
    ap.add_argument("--task-dir", required=True, help="题包目录（生成 <task-dir>/jobs/）")
    ap.add_argument("--summary", required=True, help="资格汇总 model_runs_summary_*.json")
    ap.add_argument("--repo-root", default=None, help="用于计算来源相对路径（默认自动推断）")
    ap.add_argument("--local-verification", default=None, help="额外归档的本机复核证据目录/文件")
    ap.add_argument(
        "--with-readme",
        action="store_true",
        help="额外生成 jobs/README.md（默认不生成：口径与缺口声明已内嵌在 job.json / agent/run.json / verifier/result.json）",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    task_dir = Path(args.task_dir).resolve()
    if not (task_dir / "task.toml").is_file():
        raise SystemExit(f"不是题包目录（缺 task.toml）：{task_dir}")
    summary_path = Path(args.summary).resolve()
    summary = load_summary(summary_path)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else None
    if repo_root is None:
        for parent in summary_path.parents:
            if (parent / "harbor-windows").is_dir():
                repo_root = parent
                break
    if repo_root is None:
        repo_root = summary_path.parent
    try:
        summary_rel = summary_path.relative_to(repo_root).as_posix()
    except ValueError:
        summary_rel = summary_path.as_posix()

    jobs = collect_jobs(summary)
    task_id = summary.get("task_id") or task_dir.name
    task_versions = summary.get("task_versions") or []

    if len(task_versions) == 1:
        task_version = task_versions[0]
    else:
        seen = {j["run"].get("task_version") for j in jobs}
        task_version = ",".join(sorted(v for v in seen if v)) or "unknown"

    jobs_root = task_dir / "jobs"
    if args.dry_run:
        print(f"[dry-run] 目标 {jobs_root}")
        print(f"[dry-run] task_id={task_id} task_version={task_version} jobs={len(jobs)}")
        for job in jobs:
            flag = " [excluded]" if job["excluded"] else ""
            print(f"  - {job['run']['run_id']}  mode={job['run'].get('mode')}{flag}")
        return 0

    if jobs_root.exists():
        shutil.rmtree(jobs_root)
    (jobs_root / "_index").mkdir(parents=True)

    index_rows = []
    for job in jobs:
        run = job["run"]
        job_id = run["run_id"]
        job_dir = jobs_root / job_id
        (job_dir / "agent").mkdir(parents=True)
        (job_dir / "verifier").mkdir(parents=True)
        job_json, agent_json, verifier_json = build_job_payload(job, summary, summary_rel)
        write_json(job_dir / "job.json", job_json)
        write_json(job_dir / "agent" / "run.json", agent_json)
        write_json(job_dir / "verifier" / "result.json", verifier_json)
        index_rows.append(
            {
                "job_id": job_id,
                "mode": run.get("mode"),
                "role": job["role"],
                "model_key": job["model_key"] or "",
                "model_label": run.get("run_label") or "",
                "verdict": run.get("verdict"),
                "report_status": run.get("report_status"),
                "agent_status": run.get("agent_status") or "",
                "turns": run.get("turns") if run.get("turns") is not None else "",
                "duration_seconds": run.get("duration_seconds"),
                "excluded": "true" if job["excluded"] else "false",
                "exclusion_summary": (job["exclusion"] or {}).get("summary", "")
                if job["excluded"]
                else "",
                "test_log_sha256": run.get("test_log_sha256") or "",
                "original_result_path": run.get("result_path") or "",
            }
        )

    write_json(jobs_root / "_index" / "qualification_summary.json", summary)
    with (jobs_root / "_index" / "jobs_index.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(index_rows[0].keys()))
        writer.writeheader()
        writer.writerows(index_rows)

    extra: list[str] = []
    if args.local_verification:
        src = Path(args.local_verification).resolve()
        if not src.exists():
            raise SystemExit(f"复核证据路径不存在：{src}")
        extra = copy_local_verification(src, jobs_root / "_local_verification")

    if args.with_readme:
        (jobs_root / "README.md").write_text(
            render_readme(task_id, task_version, summary_rel, jobs, extra), encoding="utf-8"
        )

    hits = scan_secrets(jobs_root)
    if hits:
        print("!! 生成内容命中疑似凭据模式，请人工复核：", file=sys.stderr)
        for h in hits:
            print(f"   - {h}", file=sys.stderr)
        return 2

    print(f"task_id={task_id} task_version={task_version}")
    print(f"jobs={len(jobs)}（excluded={sum(1 for j in jobs if j['excluded'])}）")
    print(f"输出：{jobs_root}")
    if extra:
        print(f"本机复核证据：{len(extra)} 项")
    print("凭据扫描：未命中")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
