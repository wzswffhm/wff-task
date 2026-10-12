# -*- coding: utf-8 -*-
"""assemble_218_jobs_archive.py —— 为 wfflab__wlogseg-218 组装 jobs/ 归档。

口径与 215/216 一致（schema `harbor-independent-jobs-archive-v1`、archive_only），
但**来源如实不同**，脚本不掩盖这一点：

  215/216 的 14 轮由本地 Outside-Harbor runner（runner.py + Windows 容器）执行；
  218 的轮次由模型调用层 `skills/harbor-windows/scripts/agent_harness.py`（宿主即
  真实 Windows Runtime，无容器）执行，判分由 `_qc_runs/wlogseg-build/judge_runs.py`
  驱动题包自带 `tests/test.ps1` 完成。故：

  * 不写 `docker_image` / `docker_image_digest`（例如实般留 null 并在 note 说明无容器）；
  * 不伪造 `agent.log` / `raw-runner-result.json`（这些产物在 218 不存在）；
  * 每条 trial 的 `evidence_source` 写明真实来源目录与缺失项。

本脚本 archive-only：不新增执行、不产生新的 run/score/response。

用法：
    python assemble_218_jobs_archive.py [--out DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG_NAME = "wfflab__wlogseg-218-v1.0.0-delivery"
PKG = ROOT / "harbor-windows" / PKG_NAME
TASK_ID = "wfflab__wlogseg-218"
TASK_NAME = "wfflab/wlogseg-218"
TASK_VERSION = "1.0.0"
RUNS = PKG / "extras" / "model_runs"
CONTROLS = ROOT / "harbor-windows" / "_qc_runs" / "wlogseg-build" / "controls-218"
DEFAULT_OUT = PKG

SCHEMA = "harbor-independent-jobs-archive-v1"
AGENT_ENGINE = "harbor-windows/skills/harbor-windows/scripts/agent_harness.py"
VERIFIER_ENGINE = "_qc_runs/wlogseg-build/judge_runs.py -> tests/test.ps1"

MODEL_ROUNDS = [
    ("glm-5.3", 1),
    ("kimi-k3", 1),
    ("opus-5", 1), ("opus-5", 2), ("opus-5", 3),
    ("qwen3.8-max-0902", 1), ("qwen3.8-max-0902", 2), ("qwen3.8-max-0902", 3),
]
# (控制轮 case 名, 角色) —— 控制轮与 215/216 同序：nop 在前、oracle 在后
CONTROL_ROUNDS = [
    ("nop-1", "nop"), ("nop-2", "nop"), ("nop-3", "nop"),
    ("golden-1", "oracle"), ("golden-2", "oracle"), ("golden-3", "oracle"),
]

MODEL_LABEL_META = {
    "qwen3.8-max-0902": ("Qwen3.8-Max-0902", "QWEN"),
    "opus-5": ("Opus 5", "OPUS"),
    "glm-5.3": ("GLM-5.3", "GLM"),
    "kimi-k3": ("Kimi K3", "KIMI"),
}


# --------------------------------------------------------------------- helpers
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8", newline="\n")


def write_text(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def trial_name(seed: str, control: bool) -> str:
    """稳定生成 7 字符 trial 后缀（可复现，不用随机数）。"""
    h = sha256_bytes(seed.encode("utf-8"))
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    n = int(h[:16], 16)
    out = []
    for _ in range(7):
        out.append(alphabet[n % 62])
        n //= 62
    return ("task0__" if control else "task__") + "".join(out)


def tree_hash(task_dir: Path) -> str:
    """题包树 hash：排除 jobs/、extras/、缓存（与平台口径一致）。"""
    skip = {"jobs", "extras", "__pycache__", ".pytest_cache", ".mypy_cache", ".git"}
    digest = hashlib.sha256()
    files = sorted(p for p in task_dir.rglob("*")
                   if p.is_file() and not (set(p.relative_to(task_dir).parts) & skip))
    for f in files:
        rel = f.relative_to(task_dir).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(sha256_file(f).encode("ascii"))
    return digest.hexdigest()


def copy_into(src: Path, dst: Path) -> dict:
    """复制单个文件并返回 {name, sha256, size}；src 缺失时如实返回 exists=False。"""
    if not src.is_file():
        return {"name": dst.name, "exists": False}
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {"name": dst.name, "exists": True,
            "sha256": sha256_file(dst), "size": dst.stat().st_size}


# --------------------------------------------------------------------- 单轮组装
def build_model_trial(trial: str, model_dir: str, run_index: int, jobs_dir: Path) -> dict:
    rd = RUNS / model_dir / ("run-%d" % run_index)
    meta = read_json(rd / "meta.json", {}) or {}
    rep = read_json(rd / "report.json", {}) or {}
    label, alias = MODEL_LABEL_META[model_dir]
    tdir = jobs_dir / trial
    agent = tdir / "agent"
    ver = tdir / "verifier"

    files = {}
    for src_name, dst in (
        ("agent_result.json", agent / "agent-result.json"),
        ("meta.json", agent / "meta.json"),
        ("trajectory.jsonl", agent / "trajectory.jsonl"),
        ("patch.diff", agent / "patch.diff"),
        ("response.md", agent / "response.md"),
    ):
        files["agent/" + dst.name] = copy_into(rd / src_name, dst)

    write_text(agent / "prompt.task.txt",
               (PKG / "instruction.md").read_text(encoding="utf-8"))
    files["agent/prompt.task.txt"] = {"name": "prompt.task.txt", "exists": True}

    # verifier 侧：judge_runs 的证据目录
    case = "%s_r%d" % (model_dir.replace("-", "_").replace(".", "_"), run_index)
    vdir = RUNS / "_judge" / (case + "__verifier")
    for src_name, dst in (
        (f"{case}.summary.json", ver / "summary.json"),
        ("result.json", ver / "result.json"),
        ("checks.json", ver / "checks.json"),
        (f"{case}.stdout.log", ver / "stdout.log"),
    ):
        files["verifier/" + dst.name] = copy_into(vdir / src_name, dst)

    # 逐 testcase 结果（题包 model_runs 里的 per_testcase.json）
    files["verifier/per-testcase.json"] = copy_into(rd / "per_testcase.json",
                                                    ver / "per-testcase.json")

    reward = rep.get("score")
    write_text(ver / "reward.txt", "" if reward is None else str(reward))
    files["verifier/reward.txt"] = {"name": "reward.txt", "exists": True}

    judge = rep.get("judge") or {}
    identity = {
        "task_id": TASK_ID, "task_name": TASK_NAME, "task_version": TASK_VERSION,
        "task_hash": tree_hash(PKG),
        "task_hash_algorithm": ("sha256 over (relative posix path + sha256(file content)) "
                                "for every file in the task tree, excl. jobs/, extras/, caches"),
        "docker_image": None, "docker_image_digest": None,
        "container_note": ("218 未使用容器：模型在宿主真实 Windows Runtime 的沙箱目录中执行"
                           "（agent_harness.py），判分由题包 tests/test.ps1 在本机执行。"),
    }
    config = {
        "task": {"path": PKG_NAME},
        "trial_name": trial,
        "trials_dir": "jobs",
        "agent": {"name": "harbor-windows:AgentHarness(LocalModelRunner)",
                  "kwargs": {"alias": alias, "label": model_dir, "run_index": run_index,
                             "model": meta.get("model_identity"),
                             "base_url": meta.get("base_url")}},
        "environment": {"import_path": "host-windows-runtime:no-container",
                        "force_build": False, "kwargs": {}},
        "verifier": {"import_path": "task:tests/test.ps1"},
        "job_id": sha256_bytes(("218|%s|%d" % (model_dir, run_index)).encode())[:32],
    }
    write_json(tdir / "config.json", config)

    result = {
        "id": config["job_id"],
        "task_name": TASK_NAME,
        "trial_name": "%s__%s-run%d" % (TASK_ID, model_dir, run_index),
        "trial_uri": "jobs/%s" % trial,
        "task_id": {"path": PKG_NAME},
        "task_checksum": identity["task_hash"],
        "config": config,
        "agent_info": {"name": "harbor-windows:AgentHarness(LocalModelRunner)",
                       "version": None,
                       "model_info": {"alias": alias, "label": model_dir,
                                      "base_url": meta.get("base_url")}},
        "agent_result": {
            "n_input_tokens": meta.get("input_tokens"),
            "n_cache_tokens": None,
            "n_output_tokens": meta.get("output_tokens"),
            "cost_usd": None,
            "rollout_details": None,
            "metadata": {
                "alias": alias, "model": meta.get("model_identity"),
                "role": "candidate", "task_id": TASK_ID, "task_version": TASK_VERSION,
                "workspace": meta.get("sandbox"),
                "credentials_on_host_only": True,
                "engine": AGENT_ENGINE,
                "run_index": run_index,
                "steps": meta.get("steps"),
                "submitted": meta.get("submitted"),
                "elapsed_sec": meta.get("elapsed"),
                "patch_bytes": meta.get("patch_bytes"),
                "result": {"status": meta.get("status"),
                           "invalid_reason": meta.get("invalid_reason")},
            },
        },
        "verifier_result": {"rewards": {"reward": reward}},
        "verifier_environment_mode": "host",
        "exception_info": None,
        "started_at": meta.get("started_at_utc"),
        "finished_at": meta.get("completed_at_utc"),
        "evidence_source": {
            "engine": AGENT_ENGINE,
            "verifier_engine": VERIFIER_ENGINE,
            "source_run_dir": str(rd.relative_to(ROOT)).replace("\\", "/"),
            "source_verifier_dir": str(vdir.relative_to(ROOT)).replace("\\", "/"),
            "files": {k: v for k, v in files.items() if v.get("exists")},
            "missing_files": sorted(k for k, v in files.items() if not v.get("exists")),
            "run_time_identity": identity,
            "run_time_identity_note": (
                "本 trial 的执行与判分均发生在宿主真实 Windows Runtime；未产出容器 "
                "agent.log / raw-runner-result.json，故不提供、也不伪造。"),
        },
        "judge": judge,
    }
    write_json(tdir / "result.json", result)
    write_text(tdir / "trial.log",
               "trial %s (%s run-%d)\nengine=%s\nverifier=%s\nscore=%s\n"
               % (trial, model_dir, run_index, AGENT_ENGINE, VERIFIER_ENGINE, reward))
    return {"trial_name": trial, "kind": "model", "label": model_dir,
            "original_job_name": "218-%s-run%d" % (model_dir, run_index),
            "original_job_id": config["job_id"], "score": reward,
            "original_config": config, "result_path": "jobs/%s/result.json" % trial,
            "evidence_source": result["evidence_source"]}


def build_control_trial(trial: str, case: str, role: str, jobs_dir: Path) -> dict:
    summ = read_json(CONTROLS / ("%s.summary.json" % case), {}) or {}
    vdir_src = CONTROLS / (case + "__verifier")
    tdir = jobs_dir / trial
    agent = tdir / "agent"
    ver = tdir / "verifier"

    files = {}
    files["verifier/result.json"] = copy_into(vdir_src / "result.json", ver / "result.json")
    files["verifier/checks.json"] = copy_into(vdir_src / "checks.json", ver / "checks.json")
    files["verifier/stdout.log"] = copy_into(vdir_src / (case + ".stdout.log"),
                                             ver / "stdout.log")
    if role == "oracle":
        files["agent/oracle-application.json"] = copy_into(
            vdir_src / (case + ".solve.log"), agent / "oracle-application.json")
    else:
        write_json(agent / "no-agent.json", {
            "mode": "no-change", "description": "未注入任何补丁，按交付初始态直接判分",
            "derived_by": "assemble_218_jobs_archive.py"})
        files["agent/no-agent.json"] = {"name": "no-agent.json", "exists": True}

    write_text(agent / "prompt.task.txt", (PKG / "instruction.md").read_text(encoding="utf-8"))
    files["agent/prompt.task.txt"] = {"name": "prompt.task.txt", "exists": True}

    score = summ.get("score")
    write_text(ver / "reward.txt", "" if score is None else str(score))
    files["verifier/reward.txt"] = {"name": "reward.txt", "exists": True}

    identity = {
        "task_id": TASK_ID, "task_name": TASK_NAME, "task_version": TASK_VERSION,
        "task_hash": tree_hash(PKG),
        "docker_image": None, "docker_image_digest": None,
        "container_note": "控制轮由本机真实 Windows Runtime 执行（无容器）。",
    }
    config = {
        "task": {"path": PKG_NAME},
        "trial_name": trial,
        "trials_dir": "jobs",
        "agent": {"name": "harbor-windows:ControlTrial",
                  "kwargs": {"alias": "CONTROL", "label": "golden" if role == "oracle" else "no-change",
                             "case": case}},
        "environment": {"import_path": "host-windows-runtime:no-container",
                        "force_build": False, "kwargs": {}},
        "verifier": {"import_path": "task:tests/test.ps1"},
        "job_id": sha256_bytes(("218|%s" % case).encode())[:32],
    }
    write_json(tdir / "config.json", config)
    result = {
        "id": config["job_id"],
        "task_name": TASK_NAME,
        "trial_name": "%s__%s" % (TASK_ID, case),
        "trial_uri": "jobs/%s" % trial,
        "task_id": {"path": PKG_NAME},
        "task_checksum": identity["task_hash"],
        "config": config,
        "agent_info": {"name": "harbor-windows:ControlTrial", "version": None,
                       "model_info": {"alias": "CONTROL",
                                      "label": "golden" if role == "oracle" else "no-change"}},
        "agent_result": {
            "n_input_tokens": None, "n_cache_tokens": None, "n_output_tokens": None,
            "cost_usd": None, "rollout_details": None,
            "metadata": {"role": role, "case": case,
                         "oracle_apply_exit": summ.get("oracle_apply_exit"),
                         "expected_score": summ.get("expected_score"),
                         "engine": "run_218_controls.py"},
        },
        "verifier_result": {"rewards": {"reward": score}},
        "verifier_environment_mode": "host",
        "exception_info": None,
        "started_at": None, "finished_at": None,
        "judge": {"engine": "tests/test.ps1 (本机真实 Windows Runtime)",
                  "run_validity": summ.get("run_validity"),
                  "total": summ.get("total"), "passed": summ.get("passed"),
                  "failed": summ.get("failed"), "elapsed_sec": summ.get("elapsed")},
        "evidence_source": {
            "engine": "_qc_runs/wlogseg-build/run_218_controls.py",
            "verifier_engine": VERIFIER_ENGINE,
            "source_verifier_dir": str(vdir_src.relative_to(ROOT)).replace("\\", "/"),
            "files": {k: v for k, v in files.items() if v.get("exists")},
            "missing_files": sorted(k for k, v in files.items() if not v.get("exists")),
            "run_time_identity": identity,
            "run_time_identity_note": "控制轮为本机 Windows Runtime 直跑，无容器产物。",
        },
    }
    write_json(tdir / "result.json", result)
    write_text(tdir / "trial.log",
               "trial %s (%s)\nexpected_score=%s actual=%s validity=%s\n"
               % (trial, case, summ.get("expected_score"), score, summ.get("run_validity")))
    return {"trial_name": trial, "kind": "control", "label": role,
            "original_job_name": "218-%s" % case,
            "original_job_id": config["job_id"], "score": score,
            "original_config": config, "result_path": "jobs/%s/result.json" % trial,
            "evidence_source": result["evidence_source"]}


# --------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args()
    out = Path(a.out).resolve()
    jobs = out / "jobs"
    if jobs.exists():
        shutil.rmtree(jobs)
    jobs.mkdir(parents=True)

    trials = []
    for model_dir, n in MODEL_ROUNDS:
        tn = trial_name("218|model|%s|%d" % (model_dir, n), control=False)
        print("  model   %-20s run-%d -> %s" % (model_dir, n, tn), flush=True)
        trials.append(build_model_trial(tn, model_dir, n, jobs))
    for case, role in CONTROL_ROUNDS:
        tn = trial_name("218|control|%s" % case, control=True)
        print("  control %-12s -> %s" % (case, tn), flush=True)
        trials.append(build_control_trial(tn, case, role, jobs))
    n_model = sum(1 for t in trials if t["kind"] == "model")
    n_ctl = sum(1 for t in trials if t["kind"] == "control")
    desc = ("Packaging-only aggregation of the 218 task-version rounds. No new execution, run ID, "
            "score, response or task checksum was created. Candidate rounds were executed by "
            "skills/harbor-windows/scripts/agent_harness.py on the host's real Windows runtime; "
            "control rounds (oracle x3 / no-change x3) and every grading step were executed by "
            "tests/test.ps1 through _qc_runs/wlogseg-build/{run_218_controls,judge_runs}.py. "
            "No container was involved, so container-only artefacts are absent by design.")

    config = {
        "schema": SCHEMA, "archive_only": True, "description": desc,
        "task_id": TASK_ID, "task_version": TASK_VERSION,
        "n_trials": len(trials), "n_candidate_trials": n_model, "n_control_trials": n_ctl,
        "engine_note": "host Windows runtime, no container (see evidence_source per trial)",
        "trials": [{k: t[k] for k in ("trial_name", "original_job_name", "original_job_id",
                                      "original_config", "kind", "label", "score")}
                   for t in trials],
    }
    write_json(jobs / "config.json", config)

    result = {
        "schema": SCHEMA, "archive_only": True, "description": desc,
        "task_id": TASK_ID, "task_version": TASK_VERSION,
        "n_total_trials": len(trials),
        "trials": [{"trial_name": t["trial_name"],
                    "original_job_name": t["original_job_name"],
                    "original_job_id": t["original_job_id"],
                    "trial_result": t["result_path"],
                    "score": t["score"],
                    "kind": t["kind"], "label": t["label"],
                    "evidence_source": t["evidence_source"]} for t in trials],
    }
    write_json(jobs / "result.json", result)

    source_mapping = []
    for p in sorted(jobs.rglob("*")):
        if p.is_file() and p.name != "lock.json":
            source_mapping.append({
                "path": p.relative_to(jobs).as_posix(),
                "sha256": sha256_file(p), "size": p.stat().st_size})
    lock = {
        "schema": SCHEMA, "archive_only": True, "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "package_tree_sha256": tree_hash(PKG),
        "package_tree_sha256_algorithm": ("sha256 over (relative posix path + sha256(file)) "
                                          "of every file under the package, excl. jobs/, extras/, caches"),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_mapping": source_mapping,
    }
    write_json(jobs / "lock.json", lock)

    joblog = []
    for t in trials:
        joblog.append("===== Original job: %s =====" % t["original_job_name"])
        joblog.append("trial=%s kind=%s label=%s score=%s"
                      % (t["trial_name"], t["kind"], t["label"], t["score"]))
        joblog.append("engine=%s" % t["evidence_source"].get("engine"))
        joblog.append("")
    write_text(jobs / "job.log", "\n".join(joblog))

    write_text(jobs / "README.md", (
        "# jobs/ 归档说明（wfflab__wlogseg-218）\n\n"
        "本目录按 `%s`（archive-only）重组 218 的 %d 轮证据：候选模型 %d 轮 + 控制轮 %d 轮。\n\n"
        "## 与 215/216 的差异（如实声明，不伪造）\n\n"
        "| 项 | 215 / 216 | 218（本包） |\n|---|---|---|\n"
        "| 执行引擎 | 本地 Outside-Harbor runner + Windows 容器 | `agent_harness.py`，宿主真实 Windows Runtime（无容器） |\n"
        "| 判分 | 容器内 tests/test.ps1 | 本机 tests/test.ps1（`judge_runs.py` / `run_218_controls.py` 驱动） |\n"
        "| `docker_image` / digest | 有 | **无**（字段留 null，`container_note` 说明） |\n"
        "| `agent/agent.log` | 有 | **未产出**（原始轨迹为 `agent/trajectory.jsonl`） |\n"
        "| `verifier/raw-runner-result.json` | 有 | **未产出**（原始判分产物为 `verifier/result.json` + `checks.json`） |\n\n"
        "每个 trial 的 `result.json → evidence_source` 里写明了真实来源目录与缺项清单，"
        "未留存的产物一律不提供、不伪造。\n\n"
        "## 分数\n\n"
        "%s\n" % (SCHEMA, len(trials), n_model, n_ctl,
                  "\n".join("- `%s`（%s）：%s" % (t["trial_name"], t["original_job_name"], t["score"])
                            for t in trials))))

    print("jobs/ 组装完成：%d 轮（模型 %d + 控制 %d）→ %s" % (len(trials), n_model, n_ctl, jobs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
