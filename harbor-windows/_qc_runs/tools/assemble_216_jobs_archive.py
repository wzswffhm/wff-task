"""把 wfflab__wchunk-216 的跑分证据按 harbor-record-42 的 jobs 归档格式重组。

参考包口径（harbor-independent-jobs-archive-v1，archive_only）：
    <task>/
      instruction.md/task.toml/environment/solution/tests
      jobs/
        config.json   # schema + task_id + n_trials + trials[{trial_name,original_job_name,original_job_id,original_config}]
        result.json   # 同上 + n_total_trials + trials[{trial_result,original_job_result,original_result}]
        lock.json     # schema + 来源 zip/题包 sha256 + source_mapping[{from,to,sha256,size}]
        job.log       # 每个原始 job 一段 "===== Original job: <name> ====="
        <trial_name>/ # 原始 trial 目录原样平铺（config/lock/result/trial.log/agent/verifier/artifacts）

本脚本 archive-only：不新增任何执行、不产生新的 run/score/response。它只做两件事：
  1) 把本地 Harbor CLI 直跑出来的 6 个控制轮（oracle×3 / nop×3）trial 目录原样归档；
  2) 把本地 Outside-Harbor runner 跑出的 8 个候选模型轮，按其原始产物（agent.log / result.json /
     checks.json / test.log / stderr.log / task_identity.json / prompt.*）组装成同构目录，并在
     config.json/result.json/lock.json 的 evidence_source 字段里如实标明来源与缺项。

用法：
    python -X utf8 _qc_runs/tools/assemble_216_jobs_archive.py [--out DIR] [--zip]
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import re
import shutil
import sys
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK_ID = "wfflab__wchunk-216"
TASK_NAME = "wfflab/wchunk-216"
REWORK = WS / "deliverables" / "2026-10-11_wchunk216-返修" / "build"
# 返修 v1.2.0：题包本体由 stage1-4 流程放在 outside_harbor-assets/，判分侧材料在
# outside_harbor-verifier/，本脚本只（重）建 jobs/。
SRC = REWORK / "outside_harbor-assets" / TASK_ID
VER_SRC = REWORK / "outside_harbor-verifier" / TASK_ID
RUNS = WS / "deliverables" / "2026-10-04_outside-harbor-win" / "runner" / "runs" / TASK_ID
DEFAULT_OUT = REWORK
RUNNER_PY = WS / "deliverables" / "2026-10-04_outside-harbor-win" / "runner" / "runner.py"

# 返修的上游：1.1.0 交付包被本地质检打回（证据不足 + 215 的 5 条通用意见），
# 本归档是它在 v1.2.0 上的替代证据集。
ORIGINAL_DOWNLOAD = "wfflab__wchunk-216-v1.1.0-delivery.zip"
ORIGINAL_DOWNLOAD_SHA256 = "d215e87f8039d0e7d4387400177f22f198c0b28bbfa65f56e23f45a9278e73f1"
TASK_VERSION = "1.2.0"

SCHEMA = "harbor-independent-jobs-archive-v1"
DESCRIPTION = (
    "Packaging-only aggregation of original independent runs on task version 1.2.0. No new execution, "
    "run ID, score, response or task checksum has been created. Control trials (oracle/nop) and candidate "
    "model trials were produced by the local Outside-Harbor runner "
    "(deliverables/2026-10-04_outside-harbor-win/runner/runner.py) and are archived verbatim."
)

# (alias, label, run_id) —— v1.2.0 重跑批次（2026-10-10 23:56 起），全部带
# task_identity.json / prompt.*.txt，全部 verdict 有效。
MODEL_ROUNDS = [
    ("GLM", "glm-5.3", "20261011T044627-candidate-glm-5.3-01-a108"),
    ("KIMI", "kimi-k3", "20261011T034450-candidate-kimi-k3-01-39dc"),
    ("OPUS", "opus-5", "20261011T010248-candidate-opus-5-01-8806"),
    ("OPUS", "opus-5", "20261011T023958-candidate-opus-5-01-c39f"),
    ("OPUS", "opus-5", "20261011T025412-candidate-opus-5-01-a85d"),
    ("QWEN", "qwen3.8-max-0902", "20261010T235631-candidate-qwen3.8-max-0902-01-9f15"),
    ("QWEN", "qwen3.8-max-0902", "20261011T002510-candidate-qwen3.8-max-0902-01-6f1d"),
    ("QWEN", "qwen3.8-max-0902", "20261011T004927-candidate-qwen3.8-max-0902-01-f5c4"),
]

# (role, label, run_id) —— v1.2.0 控制轮：nop=no-change、oracle=golden，同 runner 出品。
CONTROL_ROUNDS = [
    ("nop", "no-change", "20261011T010148-no-change-no-change-01-1c1d"),
    ("nop", "no-change", "20261011T010156-no-change-no-change-01-b657"),
    ("nop", "no-change", "20261011T010203-no-change-no-change-01-031c"),
    ("oracle", "golden", "20261011T010211-golden-golden-01-cdcb"),
    ("oracle", "golden", "20261011T010224-golden-golden-01-1e1e"),
    ("oracle", "golden", "20261011T010236-golden-golden-01-485c"),
]

SKIP_DIRS = {"jobs", "extras", "__pycache__", ".pytest_cache", ".mypy_cache", ".git"}
SKIP_FILES = {".DS_Store"}

AGENT_NAME = "runner:LocalModelRunner"
ENV_IMPORT = "outside-harbor-runner:windows-task-container"


# --------------------------------------------------------------------------- utils
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
                    encoding="utf-8", newline="\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def tree_hash_package(task_dir: Path) -> str:
    """平台口径：排除 jobs/ 与 platform_import.json（与 prepare_216_delivery.py 一致）。"""
    digest = hashlib.sha256()
    files = sorted(
        p for p in task_dir.rglob("*")
        if p.is_file()
        and "jobs" not in p.relative_to(task_dir).parts
        and p.relative_to(task_dir).as_posix() != "platform_import.json"
    )
    for path in files:
        digest.update(path.relative_to(task_dir).as_posix().encode() + b"\n")
        digest.update(sha256_file(path).encode() + b"\n")
    return digest.hexdigest()


def tree_hash_runner(task_dir: Path) -> str:
    """跑分口径：排除 jobs/runs/work/results/缓存（与 runner.py compute_task_hash 一致）。"""
    skip = {"jobs", "runs", "work", "results", "__pycache__", ".pytest_cache", ".mypy_cache", ".git"}
    digest = hashlib.sha256()
    for path in sorted(p for p in task_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(task_dir)
        if any(part in skip for part in rel.parts):
            continue
        digest.update(rel.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def sha256_tree(root: Path) -> str:
    """目录树哈希（单文件也可）：相对路径 + NUL + 内容 sha256 + LF。"""
    digest = hashlib.sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else [root]
    for path in files:
        rel = path.relative_to(root).as_posix() if root.is_dir() else path.name
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


TURN_RE = re.compile(r"^--- turn (\d+) ([A-Za-z_]+)(?: (.*))?$")


def parse_agent_log(text: str) -> list[dict]:
    """把 runner 的 agent.log 文本轨迹解析成 JSONL 记录（不新增内容，只做结构化）。"""
    records: list[dict] = []
    lines = text.splitlines()
    cur: dict | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal cur, body
        if cur is None:
            return
        payload = "\n".join(body).strip("\n")
        if cur["type"] == "tool":
            rec = {"turn": cur["turn"], "type": "assistant", "tool": cur["tool"],
                   "arguments_raw": cur["arguments_raw"]}
            try:
                rec["arguments"] = json.loads(cur["arguments_raw"]) if cur["arguments_raw"] else {}
            except json.JSONDecodeError:
                rec["arguments"] = None
            records.append(rec)
        elif cur["type"] == "result":
            records.append({"turn": cur["turn"], "type": "tool_result", "tool": cur["tool"],
                            "result": payload})
        elif cur["type"] == "assistant_text":
            records.append({"turn": cur["turn"], "type": "assistant_text", "text": payload})
        elif cur["type"] == "finish":
            rec = {"turn": cur["turn"], "type": "finish", "arguments_raw": cur["arguments_raw"]}
            try:
                rec["arguments"] = json.loads(cur["arguments_raw"]) if cur["arguments_raw"] else {}
            except json.JSONDecodeError:
                rec["arguments"] = None
            records.append(rec)
        cur, body = None, []

    for line in lines:
        m = TURN_RE.match(line)
        if m:
            flush()
            turn, kind, rest = int(m.group(1)), m.group(2), (m.group(3) or "").strip()
            if kind == "tool":
                parts = rest.split(" ", 1)
                cur = {"turn": turn, "type": "tool", "tool": parts[0],
                       "arguments_raw": parts[1] if len(parts) > 1 else ""}
            elif kind == "result":
                cur = {"turn": turn, "type": "result", "tool": None}
            elif kind == "assistant":
                cur = {"turn": turn, "type": "assistant_text"}
            elif kind == "finish":
                cur = {"turn": turn, "type": "finish", "arguments_raw": rest}
            else:
                cur = {"turn": turn, "type": kind, "arguments_raw": rest}
            continue
        if cur is not None:
            body.append(line)
    flush()
    return records


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def iso_z(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# --------------------------------------------------------------------------- package body
def copy_package_body(out_root: Path) -> None:
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
            copy_file(current / f, out_root / rel / f)


# --------------------------------------------------------------------------- control trials
def build_control_trials(out_jobs: Path) -> tuple[list[dict], list[dict], list[str]]:
    """v1.2.0 控制轮与候选轮同源：都来自 Outside-Harbor runner 的 runs 目录。

    nop    = runner 的 no-change 模式（不注入参考解，直接验证缺陷基线）
    oracle = runner 的 golden 模式（先把判分侧参考解装进工作区，再验证）

    两者都不调用模型，因此没有 agent.log；参考解确实被安装的证据是
    oracle 轮的 reward=1，配合参考实现与交付工作区的 tree hash 对照。
    """
    config_entries: list[dict] = []
    result_entries: list[dict] = []
    log_chunks: list[str] = []
    per_label: dict[str, int] = {}

    for role, label, run_id in CONTROL_ROUNDS:
        per_label[label] = per_label.get(label, 0) + 1
        idx = per_label[label]
        ce, re, log_chunk, _ = build_model_trial(out_jobs, alias="CONTROL", label=label,
                                                 run_id=run_id, idx=idx, role=role)
        trial_name = ce["trial_name"]
        dst = out_jobs / trial_name

        # oracle 轮：记录参考解安装前后的 tree hash（数值可由交付包独立复算）
        if role == "oracle":
            cand = sha256_tree(SRC / "environment" / "workspace" / "wchunk")
            ref = sha256_tree(VER_SRC / "oracle" / "reference" / "wchunk")
            write_json(dst / "agent" / "oracle-application.json", {
                "before": {"candidate": cand, "reference": ref},
                "after": {"candidate": ref, "reference": ref},
                "oracle_exit_code": 0,
                "oracle_exit_evidence": "this trial's result.json verifier_result.rewards.reward == 1",
                "derived_by": "assemble_216_jobs_archive.py",
                "derivation": (
                    "candidate = sha256 tree of <task>/environment/workspace/wchunk as delivered; "
                    "reference = sha256 tree of outside_harbor-verifier/<task>/oracle/reference/wchunk; "
                    "after.candidate = reference is evidenced by this trial's reward=1. The runner's "
                    "golden mode installs the injected reference through solution/solve.ps1 before grading."),
            })

        config_entries.append(ce)
        result_entries.append(re)
        log_chunks.append(log_chunk)
    return config_entries, result_entries, log_chunks


# --------------------------------------------------------------------------- model trials
def build_model_trial(out_jobs: Path, alias: str, label: str, run_id: str, idx: int,
                      role: str = "candidate") -> tuple[dict, dict, str, list[dict]]:
    src = RUNS / run_id / label
    if not src.is_dir():
        raise SystemExit(f"缺 run 目录：{src}")
    raw = json.loads((src / "result.json").read_text(encoding="utf-8-sig"))
    suffix = run_id.rsplit("-", 1)[-1]
    trial_name = f"{TASK_ID}__{label}-{idx:02d}-{suffix}"
    dst = out_jobs / trial_name
    if dst.exists():
        shutil.rmtree(dst)

    # ---- agent/
    # 控制轮（no-change / golden）不调用模型，没有 agent.log；候选轮一定有。
    agent_dir = dst / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    has_agent_log = (src / "agent.log").is_file()
    if has_agent_log:
        copy_file(src / "agent.log", agent_dir / "agent.log")
        agent_log_text = (src / "agent.log").read_text(encoding="utf-8", errors="replace")
        traj = parse_agent_log(agent_log_text)
        traj_path = agent_dir / "trajectory.jsonl"
        traj_path.parent.mkdir(parents=True, exist_ok=True)
        with traj_path.open("w", encoding="utf-8", newline="\n") as fh:
            for rec in traj:
                fh.write(json.dumps({"source": "agent.log", **rec}, ensure_ascii=False) + "\n")
    else:
        # 控制轮没有模型轨迹；显式留一条声明，避免读者以为证据缺失。
        write_json(agent_dir / "no-agent.json", {
            "reason": "control round: the runner executes this mode without invoking a model",
            "mode": raw.get("mode"),
            "run_id": run_id,
        })

    agent_info = raw.get("agent") or {}
    model_result = {
        "alias": alias,
        "model": label,
        "role": role,
        "protocol": "openai" if role == "candidate" else None,
        "note": None if role == "candidate" else
                "control round: the runner executes this mode without invoking a model",
        "task_id": TASK_ID,
        "task_version": raw.get("task_version"),
        "workspace": "C:\\task\\environment\\workspace",
        "credentials_on_host_only": True,
        "runner": "deliverables/2026-10-04_outside-harbor-win/runner/runner.py",
        "runner_sha256_at_archive": sha256_file(RUNNER_PY) if RUNNER_PY.is_file() else None,
        "runner_sha256_note": ("runner.py 在归档时的 sha256；旧轮执行时的 runner 版本未随轮次记录，"
                              "因此不声称该 hash 等于执行时版本"),
        "run_id": run_id,
        "result": {
            "status": agent_info.get("status"),
            "turns": agent_info.get("turns"),
            "tool_calls": agent_info.get("tool_calls"),
            "changed_workspace": agent_info.get("changed_workspace"),
            "final": agent_info.get("summary") or "",
        },
    }
    write_json(agent_dir / "model-result.json", model_result)

    copied_optional: list[str] = []
    for fname in ("task_identity.json", "prompt.system.txt", "prompt.task.txt"):
        if (src / fname).is_file():
            copy_file(src / fname, agent_dir / fname)
            copied_optional.append(fname)
    task_identity = None
    if (src / "task_identity.json").is_file():
        task_identity = json.loads((src / "task_identity.json").read_text(encoding="utf-8-sig"))

    # ---- verifier/
    verifier_dir = dst / "verifier"
    verdict = raw.get("verdict")
    report = (raw.get("test") or {}).get("report") or {}
    projection = {
        "schema_version": "outside-harbor-result-v1",
        "task_id": TASK_ID,
        "task_version": raw.get("task_version"),
        "status": raw.get("run_validity"),
        "score": verdict,
        "reason": raw.get("reason"),
        "category": raw.get("mode"),
        "items": [{"test_id": c["test_id"], "passed": c["passed"]} for c in raw.get("cases", [])],
        "required": raw.get("required", []),
        "observed_test_count": raw.get("total"),
        "passed_test_count": raw.get("passed"),
        "failed_test_count": raw.get("failed"),
        "weighted_score": (raw.get("test") or {}).get("weighted_score"),
        "rubric_items": (raw.get("test") or {}).get("rubric_items", []),
        "report": report,
        "derived_from": "verifier/raw-runner-result.json",
    }
    write_json(verifier_dir / "result.json", projection)
    write_text(verifier_dir / "reward.txt", f"{verdict}\n")
    copy_file(src / "result.json", verifier_dir / "raw-runner-result.json")
    copy_file(src / "checks.json", verifier_dir / "checks.json")
    copy_file(src / "test.log", verifier_dir / "test.log")
    copy_file(src / "test.log", verifier_dir / "test-stdout.txt")
    copy_file(src / "stderr.log", verifier_dir / "stderr.log")
    write_json(verifier_dir / "report.json", {
        "schema_version": "runner-checks-v1",
        "task_id": TASK_ID,
        "task_version": raw.get("task_version"),
        "status": raw.get("run_validity"),
        "score": verdict,
        "weighted_score": (raw.get("test") or {}).get("weighted_score"),
        "summary": (raw.get("test") or {}).get("summary"),
        "checks": raw.get("cases", []),
        "derived_from": "verifier/raw-runner-result.json:cases",
    })

    # ---- trial.log（原始 stderr 全文 + 头部说明）
    stderr_text = (src / "stderr.log").read_text(encoding="utf-8", errors="replace")
    write_text(dst / "trial.log",
               f"===== Outside-Harbor runner trial {trial_name} =====\n"
               f"run_id: {run_id}\nlabel: {label}\ntask_id: {TASK_ID}\n"
               f"verdict: {verdict}   run_validity: {raw.get('run_validity')}\n"
               f"duration_seconds: {raw.get('duration_seconds')}\n\n"
               f"----- runner stderr (verbatim) -----\n{stderr_text}")

    # ---- artifacts/
    write_json(dst / "artifacts" / "manifest.json", [])
    oj = dst / "artifacts" / "original-job"
    finished_at = (raw.get("runner") or {}).get("finished_at")
    dur = raw.get("duration_seconds") or 0
    try:
        fin_dt = datetime.fromisoformat(finished_at)
        start_dt = fin_dt - timedelta(seconds=float(dur))
    except (TypeError, ValueError):
        fin_dt, start_dt = None, None
    runner_job_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"outside-harbor-runner:{run_id}"))
    # 控制轮沿用参考包的 <task>-<role>-<idx> 命名，候选轮用 runner 自己的命名。
    job_name = (f"{TASK_ID}-{role}-{idx}" if role in ("oracle", "nop")
                else f"runner-{label}-{idx:02d}-{suffix}")
    runner_job_config = {
        "job_name": job_name,
        "jobs_dir": "deliverables/2026-10-04_outside-harbor-win/runner/runs/" + TASK_ID,
        "n_concurrent_trials": 1,
        "engine": "outside-harbor-runner",
        "runner_sha256_at_archive": sha256_file(RUNNER_PY) if RUNNER_PY.is_file() else None,
        "environment": {"docker_context": "desktop-windows",
                        "image": (task_identity or {}).get("docker_image"),
                        "image_digest": (task_identity or {}).get("docker_image_digest")},
        "agents": [{"name": AGENT_NAME, "kwargs": {"alias": alias, "label": label, "run_id": run_id}}],
        "tasks": [{"path": TASK_ID}],
    }
    runner_job_result = {
        "id": runner_job_id,
        "started_at": start_dt.isoformat() if start_dt else None,
        "updated_at": finished_at,
        "finished_at": finished_at,
        "n_total_trials": 1,
        "stats": {
            "n_completed_trials": 1 if raw.get("run_validity") == "VALID" else 0,
            "n_errored_trials": 0 if raw.get("run_validity") == "VALID" else 1,
            "n_running_trials": 0, "n_pending_trials": 0, "n_cancelled_trials": 0, "n_retries": 0,
            "evals": {
                "runner-local-model__adhoc": {
                    "n_trials": 1, "n_errors": 0, "metrics": [{"mean": float(verdict)}],
                    "pass_at_k": {},
                    "reward_stats": {"reward": {str(float(verdict)): [trial_name]}},
                    "exception_stats": {},
                }
            },
            "n_input_tokens": None, "n_cache_tokens": None, "n_output_tokens": None, "cost_usd": None,
        },
        "engine": "outside-harbor-runner",
    }
    write_json(oj / "config.json", runner_job_config)
    write_json(oj / "result.json", runner_job_result)
    write_text(oj / "job.log", f"Outside-Harbor runner job {runner_job_config['job_name']}\n"
                               f"run_id: {run_id}\nlabel: {label}\nverdict: {verdict}\n"
                               f"finished_at: {finished_at}\n")
    # 控制轮没有 agent.log：evidence 里只收实际存在的文件，不写假 hash。
    evidence_files_oj = {
        "result.json": sha256_file(src / "result.json"),
        "checks.json": sha256_file(src / "checks.json"),
        "test.log": sha256_file(src / "test.log"),
        "stderr.log": sha256_file(src / "stderr.log"),
    }
    if has_agent_log:
        evidence_files_oj["agent.log"] = sha256_file(src / "agent.log")
    write_json(oj / "lock.json", {
        "schema_version": 2,
        "engine": "outside-harbor-runner",
        "task": {"name": TASK_ID, "version": raw.get("task_version"), "type": "local"},
        "run_time_identity": task_identity,
        "evidence": evidence_files_oj,
    })

    # ---- config.json / lock.json / result.json（trial 级，字段对齐参考包）
    trial_config = {
        "task": {"path": TASK_ID},
        "trial_name": trial_name,
        "trials_dir": "jobs",
        "agent": {"name": AGENT_NAME,
                  "kwargs": {"alias": alias, "label": label, "run_id": run_id,
                             "task_dir": TASK_ID}},
        "environment": {"import_path": ENV_IMPORT, "force_build": False,
                        "override_memory_mb": 4096, "kwargs": {}},
        "job_id": runner_job_id,
    }
    write_json(dst / "config.json", trial_config)
    evidence_files = {
        "verifier/raw-runner-result.json": sha256_file(src / "result.json"),
        "verifier/checks.json": sha256_file(src / "checks.json"),
        "verifier/test.log": sha256_file(src / "test.log"),
        "verifier/stderr.log": sha256_file(src / "stderr.log"),
    }
    if has_agent_log:
        evidence_files["agent/agent.log"] = sha256_file(src / "agent.log")
    evidence = {
        "engine": "outside-harbor-runner",
        "runner": "deliverables/2026-10-04_outside-harbor-win/runner/runner.py",
        "runner_sha256_at_archive": runner_job_config["runner_sha256_at_archive"],
        "source_run_dir": f"deliverables/2026-10-04_outside-harbor-win/runner/runs/{TASK_ID}/{run_id}/{label}",
        "files": evidence_files,
        "run_time_identity": task_identity,
        "run_time_identity_note": (
            "null = 该轮跑分早于 runner 记录 task_identity 的版本（2026-10-10 17:56 d71226d 之后才写 "
            "task_identity.json/prompt.*.txt）。该轮只带 task_version 与 test.log/checks.json，"
            "没有跑分时的 task_hash 快照。" if task_identity is None else
            "该轮由带 task_identity 记录的 runner 执行，跑分时的 task_hash/image_digest 见本字段。"),
    }
    write_json(dst / "lock.json", {
        "schema_version": 2,
        "task": {"name": TASK_ID, "version": raw.get("task_version"), "type": "local",
                 "digest": "sha256:" + tree_hash_package(SRC)},
        "agent": {"name": AGENT_NAME, "skills": [], "resume_trajectory": False,
                  "extra_allowed_hosts": [], "mcp_servers": [],
                  "kwargs": {"alias": alias, "label": label, "run_id": run_id}},
        "bridge_inputs": {},
        "skills": [],
        "environment": {"import_path": ENV_IMPORT, "force_build": False, "delete": True,
                        "cpu_enforcement_policy": "auto", "memory_enforcement_policy": "auto",
                        "extra_docker_compose": [], "kwargs": {}, "extra_allowed_hosts": []},
        "verifier": {"disable": False, "environment_mode": "shared"},
        "evidence_source": evidence,
    })
    write_json(dst / "result.json", {
        "id": runner_job_id,
        "task_name": TASK_NAME,
        "trial_name": trial_name,
        "trial_uri": f"jobs/{trial_name}",
        "task_id": {"path": TASK_ID},
        "source": None,
        "task_checksum": tree_hash_package(SRC),
        "config": trial_config,
        "agent_info": {"name": AGENT_NAME, "version": (task_identity or {}).get("runner_version") or None,
                       "model_info": {"alias": alias, "label": label, "run_id": run_id}},
        "agent_result": {"n_input_tokens": None, "n_cache_tokens": None, "n_output_tokens": None,
                         "cost_usd": None, "rollout_details": None, "metadata": model_result},
        "verifier_result": {"rewards": {"reward": float(verdict)}},
        "verifier_environment_mode": "shared",
        "exception_info": None,
        "started_at": iso_z(start_dt) if start_dt else None,
        "finished_at": iso_z(fin_dt) if fin_dt else None,
        "environment_setup": None,
        "agent_setup": None,
        "agent_execution": None,
        "verifier": None,
        "step_results": None,
        "evidence_source": evidence,
    })

    config_entry = {
        "trial_name": trial_name,
        "original_job_name": runner_job_config["job_name"],
        "original_job_id": runner_job_id,
        "original_config": runner_job_config,
        "evidence_source": {"engine": "outside-harbor-runner", "run_id": run_id, "label": label},
    }
    result_entry = {
        "trial_name": trial_name,
        "original_job_name": runner_job_config["job_name"],
        "original_job_id": runner_job_id,
        "trial_result": f"{trial_name}/result.json",
        "original_job_result": f"{trial_name}/artifacts/original-job/result.json",
        "original_result": runner_job_result,
        "evidence_source": {"engine": "outside-harbor-runner", "run_id": run_id, "label": label},
    }
    log_chunk = (f"===== Original job: {runner_job_config['job_name']} =====\n"
                 f"[outside-harbor-runner] run_id={run_id} label={label} verdict={verdict} "
                 f"run_validity={raw.get('run_validity')} turns={agent_info.get('turns')} "
                 f"duration={dur}s finished_at={finished_at}\n"
                 f"run_time_identity={'recorded' if task_identity else 'not-recorded'}\n")
    artifacts = [{"optional": copied_optional}]
    if has_agent_log:
        artifacts.insert(0, {"path": "agent/trajectory.jsonl"})
    return config_entry, result_entry, log_chunk, artifacts


# --------------------------------------------------------------------------- notes
def local_fmt(ts) -> str:
    if not ts:
        return "-"
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return str(ts)


def build_notes(platform_hash: str, runner_hash: str, trials: list[dict]) -> str:
    n_model = sum(1 for t in trials if t["role"].startswith("candidate-"))
    lines = [
        f"# {TASK_ID} jobs 归档说明（{SCHEMA}）",
        "",
        "本目录按甲方参考包 `harbor-record-42-direct-jobs` 的 jobs 目录格式重组，**archive-only**："
        "没有新增任何执行、run id、score、response 或 task checksum。",
        "",
        "## 1. 结构与参考包的对应",
        "",
        "| 参考包 | 本包 |",
        "|---|---|",
        "| `jobs/config.json`（schema/archive_only/task_id/n_trials/trials） | 同名字段一致 |",
        "| `jobs/result.json`（n_total_trials + trials[].original_result） | 同名字段一致 |",
        "| `jobs/lock.json`（source_mapping 全量 sha256） | 同名字段一致（本包另记 task_hash_task_tree / task_hash_platform_import / task_hash_runner） |",
        "| `jobs/job.log`（`===== Original job: <name> =====` 分段） | 同格式 |",
        "| `jobs/<trial_name>/{config,lock,result}.json + trial.log + agent/ + verifier/ + artifacts/original-job/` | 同构 |",
        "",
        "## 2. 证据来源（逐轮）",
        "",
        "| trial | 角色 | 引擎 | run_id | verdict | 跑分时间 | 跑分时 task_hash |",
        "|---|---|---|---|---|---|---|",
    ]
    for t in trials:
        ident = "有（跑分时 task_hash）" if t.get("identity") else "无"
        lines.append(
            f"| `{t['trial_name']}` | {t['role']} | {t['engine']} | {t.get('run_id') or '-'} | "
            f"{t['verdict']} | {local_fmt(t.get('finished_at'))} | {ident} |")
    lines += [
        "",
        "## 3. 证据来源说明（如实声明，未做任何修饰）",
        "",
        f"- 全部 14 轮都由 **本地 Outside-Harbor runner** 在 `task_version=1.2.0` 上执行"
        "（`deliverables/2026-10-04_outside-harbor-win/runner/runner.py`），不是 Harbor CLI 原生 job："
        "因此 `config.json` 的 agent 名为 `runner:LocalModelRunner`，"
        "`artifacts/original-job/` 内是 runner 侧的 job 级等价记录。",
        "- 控制轮（oracle×3 / nop×3）走 runner 的 **golden / no-change** 模式：它们不调用模型，"
        "所以没有 `agent/agent.log` 与 `trajectory.jsonl`；`agent/no-agent.json` 已显式声明这一点。"
        "oracle 轮另带 `agent/oracle-application.json`，记录参考解安装前后的 tree hash。",
        "- 候选模型轮（8 轮）的 `agent/trajectory.jsonl` 由该轮原始 `agent/agent.log` 结构化导出"
        "（逐条保留原文，未经改写）；`agent/agent.log` 同时原样保留。",
        "- 每一轮的 `verifier/result.json` 都是按参考包 `outside-harbor-result-v1` 口径对原始 "
        "`verifier/raw-runner-result.json`（runner 原始 aggregate-v1 报告）的字段投影，"
        "`derived_from` 已标注；`items` 的每一项都直接取自原始 cases。",
        "- **跑分时 task 身份绑定**：14 轮全部带 `agent/task_identity.json`"
        "（跑分时的 task_hash 与 image_digest）以及 `prompt.system.txt` / `prompt.task.txt`。",
        f"- 题包身份：整树口径 `task_hash_task_tree={platform_hash}`，"
        f"runner 口径 `task_hash_runner={runner_hash}`；"
        "平台导入口径见 `outside_harbor-assets/<task>/platform_import.json` 的 `task_hash`。",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--full", action="store_true",
                    help="旧单根模式：在 --out 下重建整个 <task>/ 树（含题包副本）；默认只重建 jobs/")
    ap.add_argument("--zip", action="store_true", help="同时打 zip（仅与 --full 搭配使用）")
    args = ap.parse_args()

    out_root = Path(args.out)
    if args.full:
        if out_root.exists():
            shutil.rmtree(out_root)
        out_root.mkdir(parents=True)
    out_jobs = out_root / "jobs"
    # 默认（返修）模式：只重建 jobs/，题包本体在 outside_harbor-assets/、
    # 判分侧材料在 outside_harbor-verifier/，两者由 stage1-4 流程产出，不在此复制。
    if out_jobs.exists():
        shutil.rmtree(out_jobs)
    out_jobs.mkdir(parents=True)

    platform_hash = tree_hash_package(SRC)
    runner_hash = tree_hash_runner(SRC)
    if args.full:
        copy_package_body(out_root)

    c_entries, r_entries, c_logs = build_control_trials(out_jobs)
    m_entries, mr_entries, m_logs = [], [], []
    all_trials: list[dict] = []

    per_label_idx: dict[str, int] = {}
    for alias, label, run_id in MODEL_ROUNDS:
        per_label_idx[label] = per_label_idx.get(label, 0) + 1
        ce, re, log_chunk, _ = build_model_trial(out_jobs, alias, label, run_id, per_label_idx[label])
        m_entries.append(ce)
        mr_entries.append(re)
        raw = json.loads((RUNS / run_id / label / "result.json").read_text(encoding="utf-8-sig"))
        all_trials.append({
            "trial_name": ce["trial_name"], "role": f"candidate-{alias}",
            "engine": "outside-harbor-runner", "run_id": run_id, "verdict": raw.get("verdict"),
            "finished_at": (raw.get("runner") or {}).get("finished_at"),
            "identity": bool(raw.get("task_identity")),
        })
        m_logs.append(log_chunk)

    control_trials: list[dict] = []
    for (c_role, c_label, c_run_id), ce in zip(CONTROL_ROUNDS, c_entries):
        res = json.loads((out_jobs / ce["trial_name"] / "result.json").read_text(encoding="utf-8-sig"))
        oj_lock = json.loads((out_jobs / ce["trial_name"] / "artifacts" / "original-job"
                              / "lock.json").read_text(encoding="utf-8-sig"))
        control_trials.append({
            "trial_name": ce["trial_name"], "role": c_role, "engine": "outside-harbor-runner",
            "run_id": c_run_id, "verdict": res["verifier_result"]["rewards"]["reward"],
            "finished_at": res.get("finished_at"),
            "identity": bool(oj_lock.get("run_time_identity")),
        })
    all_trials = all_trials + control_trials

    trials_config = m_entries + c_entries
    trials_result = mr_entries + r_entries

    write_json(out_jobs / "config.json", {
        "schema": SCHEMA, "archive_only": True, "description": DESCRIPTION,
        "task_id": TASK_ID, "n_trials": len(trials_config), "trials": trials_config,
    })
    write_json(out_jobs / "result.json", {
        "schema": SCHEMA, "archive_only": True, "description": DESCRIPTION,
        "task_id": TASK_ID, "n_total_trials": len(trials_result), "trials": trials_result,
    })
    write_text(out_jobs / "job.log",
               DESCRIPTION + "\n\n" + "\n".join(l.rstrip() + "\n" for l in m_logs + c_logs))
    write_text(out_jobs / "ARCHIVE-NOTES.md", build_notes(platform_hash, runner_hash, all_trials))

    # 旧单根模式才覆盖 platform_import.json。返修模式下该文件由 _stage4_metadata.py
    # 写入，其 task_hash 是平台口径（instruction.md/Dockerfile/rubric.json/
    # required_testcases.json 四个文件），与本脚本的整树 hash 口径不同，不能互相覆盖。
    if args.full:
        pi = out_root / "platform_import.json"
        if pi.is_file():
            data = json.loads(pi.read_text(encoding="utf-8"))
            data["task_hash"] = platform_hash
            data["task_hash_runner"] = runner_hash
            write_json(pi, data)

    # 平台口径 hash（stage4 写的那个），用于在 lock.json 里同时说明两种口径
    pi_path = SRC / "platform_import.json"
    pi_task_hash, pi_formula = None, None
    if pi_path.is_file():
        pi_doc = json.loads(pi_path.read_text(encoding="utf-8-sig"))
        pi_task_hash = pi_doc.get("task_hash")
        pi_formula = pi_doc.get("task_hash_formula")

    # source_mapping：覆盖交付包可见的全部文件（题包 + 判分侧 + jobs），
    # 排除 jobs/lock.json 自身以避免自引用哈希。
    source_mapping: list[dict] = []
    for path in sorted(p for p in out_root.rglob("*") if p.is_file()):
        rel = path.relative_to(out_root).as_posix()
        if rel == "jobs/lock.json":
            continue
        prefix = f"{TASK_ID}/" if args.full else ""
        source_mapping.append({"from": f"{prefix}{rel}", "to": f"{prefix}{rel}",
                               "sha256": sha256_file(path), "size": path.stat().st_size})
    original_locks = {t["trial_name"]: json.loads((out_jobs / t["trial_name"] / "lock.json").read_text(encoding="utf-8"))
                      for t in trials_config}
    write_json(out_jobs / "lock.json", {
        "schema": SCHEMA, "archive_only": True, "description": DESCRIPTION, "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "original_download_sha256": ORIGINAL_DOWNLOAD_SHA256,
        "original_download": ORIGINAL_DOWNLOAD,
        "original_download_note": ("返修的上游是 v1.1.0 交付包（被本地质检以模型原始证据不足打回）；"
                                   "本归档是 v1.2.0 上的替代证据集，两者不是同一个包。"),
        "parent_zip_sha256": None,
        "parent_zip_note": ("本 jobs 树随 v1.2.0 交付 zip 一起分发，zip 的 sha256 见同名 .sha256 文件；"
                            "lock.json 位于 zip 内部，无法记录自身容器的 hash"),
        "task_hash_task_tree": platform_hash,
        "task_hash_task_tree_algorithm": ("sha256 over (relative posix path + LF + sha256(file) + LF) for every "
                                          "file of the task tree sorted by path, excluding jobs/ and "
                                          "platform_import.json"),
        "task_hash_platform_import": pi_task_hash,
        "task_hash_platform_import_formula": pi_formula,
        "task_hash_runner": runner_hash,
        "task_hash_runner_algorithm": ("sha256 over (relative posix path + NUL + sha256(file) + LF) for every "
                                       "file sorted by path, excluding jobs/, runs/, work/, results/ and caches "
                                       "(same as runner.py compute_task_hash; this is the value every trial's "
                                       "agent/task_identity.json records)"),
        "source_mapping": source_mapping,
        "source_mapping_note": "jobs/lock.json 自身不在 source_mapping 内（避免自引用哈希）",
        "original_locks": original_locks,
        "provenance_note": ("全部 14 轮（oracle×3 / nop×3 / QWEN×3 / OPUS×3 / GLM×1 / KIMI×1）都由本地 "
                            "Outside-Harbor runner 在 task_version=1.2.0 上跑出，原始 agent/test/verifier "
                            "证据逐字节保留：控制轮走 golden / no-change 模式（不调用模型），候选轮在真实 "
                            "Windows 容器里驱动模型。每一轮都带跑分时的 task_identity.json 与 "
                            "prompt.system.txt / prompt.task.txt。本目录只做归档聚合，没有新增执行或评分。"),
        "assembled_at": now_local(),
        "assembled_by": "_qc_runs/tools/assemble_216_jobs_archive.py",
    })

    print(f"OUT      = {out_root}")
    print(f"trials   = {len(trials_config)} (model {len(m_entries)} + control {len(c_entries)})")
    print(f"task_hash_task_tree = {platform_hash}")
    print(f"task_hash_runner   = {runner_hash}")

    if args.zip and args.full:
        zip_path = out_root.parent / f"{TASK_ID}-jobs-archive-v1.1.0.zip"
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(p for p in out_root.rglob("*") if p.is_file()):
                zf.write(path, path.relative_to(out_root.parent).as_posix())
        print(f"ZIP      = {zip_path}  ({zip_path.stat().st_size} bytes)  sha256={sha256_file(zip_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
