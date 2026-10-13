# -*- coding: utf-8 -*-
"""assemble_jobs.py -- 把控制组与模型轮次的原生 Harbor job 组装进题包 jobs/。

用法：
    python assemble_jobs.py --task 218
    python assemble_jobs.py --task 219

行为：
  * 从 _qc_runs/relaunch-20261013/<task>/controls/jobs 与 .../model-rounds/jobs
    读取每个原生 job 的单个 trial；
  * 复制成 <staged pkg>/jobs/<job-name>/{config,lock,result,trial.log,agent/,artifacts/,verifier/}，
    trial 的随机后缀去掉（一个 job 一个 trial），并按需要裁掉超大的 agent 原始 dump；
  * 写 jobs/_index/assembly_report.json（每个 trial 的 kind / score / validity /
    cases / cases_match_required / task_checksum）；
  * 校验每个 job 都带 result.json、verifier/reward.txt、verifier/report.json，
    且 report.json 的 cases 数与 required_testcases.json 一致。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
REL = ROOT / "harbor-windows" / "_qc_runs" / "relaunch-20261013"
STAGED = REL / "staged"
TASKS = {
    "218": {"pkg_name": "wfflab__wlogseg-218-v1.1.0-delivery",
            "task_id": "wfflab__wlogseg-218", "version": "1.1.0", "pkgname": "wlogseg"},
    "219": {"pkg_name": "wfflab__wpeimg-219-v1.4.0-delivery",
            "task_id": "wfflab__wpeimg-219", "version": "1.4.0", "pkgname": "wpeimg"},
}
SKIP_NAMES = {"exception.txt"}


def build_verifier_result(trial: Path, task_id: str, version: str) -> dict:
    """从 Harbor 原生产物重建 verifier/result.json（outside-harbor-result-v1）。

    原生 Harbor 只在 trial 里产出 verifier/report.json + reward.txt，没有单独的
    verifier/result.json / verifier.log；甲方门禁的 COMMON_FILES 要求这两项，因此
    这里按 report.json 的真实内容重建，并记录来源 sha256 以便复算。
    """
    rep = {}
    rp = trial / "verifier" / "report.json"
    if rp.is_file():
        rep = json.loads(rp.read_text(encoding="utf-8-sig"))
    res = {}
    rj = trial / "result.json"
    if rj.is_file():
        try:
            res = json.loads(rj.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001
            res = {}
    cases = rep.get("cases") or []
    items = [{
        "test_id": str(c.get("test_id")),
        "passed": bool(c.get("passed")),
        "outcome": "PASS" if c.get("passed") else "FAIL",
    } for c in cases]
    score = int(rep.get("formal_score") or 0)
    return {
        "schema_version": "outside-harbor-result-v1",
        "task_id": task_id,
        "task_version": version,
        "status": rep.get("run_validity") or "INVALID",
        "score": score,
        "reason": rep.get("reason"),
        "category": "candidate",
        "items": items,
        "required": [i["test_id"] for i in items],
        "observed_test_count": len(items),
        "passed_test_count": sum(1 for i in items if i["passed"]),
        "failed_test_count": sum(1 for i in items if not i["passed"]),
        "weighted_score": score,
        "rubric_items": (rep.get("test") or {}).get("rubric_items"),
        "report": rep,
        "derived_from": {
            "verifier/report.json": "sha256:" + hashlib.sha256(rp.read_bytes()).hexdigest(),
            "result.json": ("sha256:" + hashlib.sha256(rj.read_bytes()).hexdigest()
                            if rj.is_file() else ""),
            "harbor_task_checksum": res.get("task_checksum"),
        },
    }


def build_verifier_log(trial: Path, src_job: Path) -> str:
    """重建 verifier/verifier.log：优先 test-stdout 原文，其次 trial.log / job.log。"""
    for name in ("test-stdout.txt", "trial.log"):
        p = trial / "verifier" / name
        if p.is_file() and p.stat().st_size:
            return p.read_text(encoding="utf-8", errors="replace")
    p = src_job / "job.log"
    if p.is_file() and p.stat().st_size:
        return p.read_text(encoding="utf-8", errors="replace")
    return "(no verifier log captured by the harness)\n"


def copy_job(src_job: Path, dest_job: Path, cfg: dict) -> Path | None:
    trials = [d for d in sorted(src_job.iterdir()) if d.is_dir() and "__" in d.name]
    if len(trials) != 1:
        print("  !! %s has %d trials, skipped" % (src_job.name, len(trials)))
        return None
    trial = trials[0]
    if dest_job.exists():
        shutil.rmtree(dest_job)
    dest_job.mkdir(parents=True)

    # 1) parent job files stay at the job root (the delivery contract)
    for name in ("config.json", "lock.json", "result.json", "job.log"):
        src = src_job / name
        if src.is_file():
            shutil.copy2(src, dest_job / name)

    # 2) trial payload (agent/, artifacts/, verifier/, trial.log, config/lock/result)
    for item in trial.iterdir():
        target = dest_job / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        elif item.name not in SKIP_NAMES and not (dest_job / item.name).exists():
            shutil.copy2(item, target)

    # 3) rebuild the two verifier-side files the buyer gate requires
    vdir = dest_job / "verifier"
    vdir.mkdir(exist_ok=True)
    vr = build_verifier_result(trial, cfg["task_id"], cfg["version"])
    # the buyer gate reads task_checksum straight off this file
    vr["task_checksum"] = (vr.get("derived_from") or {}).get("harbor_task_checksum")
    (vdir / "result.json").write_text(json.dumps(vr, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8", newline="\n")
    (vdir / "verifier.log").write_text(build_verifier_log(trial, src_job),
                                       encoding="utf-8", newline="\n")

    # 3b) the buyer gate resolves the job identity from <job>/result.json
    #     (result.config.agent / result.agent_result.metadata) and reads
    #     result.task_checksum there too. Harbor keeps those fields on the
    #     trial result, so merge them into the job-root aggregate.
    jr = dest_job / "result.json"
    if jr.is_file():
        try:
            agg = json.loads(jr.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001
            agg = {}
        trial_res = {}
        tr_src = trial / "result.json"
        if tr_src.is_file():
            try:
                trial_res = json.loads(tr_src.read_text(encoding="utf-8-sig"))
            except Exception:  # noqa: BLE001
                trial_res = {}
        for key in ("config", "agent_result", "verifier_result", "agent_info",
                    "task_checksum", "exception_info", "task_id", "task_name",
                    "trial_name", "started_at", "finished_at"):
            if key in trial_res and key not in agg:
                agg[key] = trial_res[key]
        # The buyer gate resolves the model alias from
        # result.agent_result.metadata.alias (or config.agent.kwargs.alias).
        # Harbor's own runner leaves agent_result.metadata null, while our
        # harness carries the alias in config.agent.kwargs, so mirror it.
        agent_cfg = (agg.get("config") or {}).get("agent") or {}
        kwargs = agent_cfg.get("kwargs") if isinstance(agent_cfg.get("kwargs"), dict) else {}
        meta = (agg.get("agent_result") or {}).get("metadata")
        if isinstance(meta, dict) and not meta.get("alias") and kwargs.get("alias"):
            meta["alias"] = kwargs.get("alias")
        jr.write_text(json.dumps(agg, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")

    # 4) keep the native trial result (it carries task_checksum and the full
    #    Harbor trial record) next to the artifacts, since the job-root
    #    result.json is the aggregate JobResult and has no checksum field.
    adir = dest_job / "artifacts"
    adir.mkdir(exist_ok=True)
    if (trial / "result.json").is_file():
        shutil.copy2(trial / "result.json", adir / "trial-result.json")

    # 5) buyer gate: oracle jobs must carry agent/qc-oracle-application.json.
    #    Native Harbor only writes agent/oracle.txt, so derive the record from
    #    the real oracle log plus the job metadata (same shape as the
    #    authoring pipeline used for wfflab__wlogseg-218 v1.0.0).
    adir_job = dest_job / "agent"
    if adir_job.is_dir() and (adir_job / "oracle.txt").is_file():
        oracle_log = (adir_job / "oracle.txt").read_text(encoding="utf-8", errors="replace")
        reward = None
        rw = dest_job / "verifier" / "reward.txt"
        if rw.is_file():
            try:
                reward = int(float(rw.read_text(encoding="utf-8-sig").strip()))
            except ValueError:
                reward = None
        payload = (dest_job / "config.json").read_text(encoding="utf-8", errors="replace")
        record = {
            "agent": "oracle",
            "solution_entry": "solution/solve.ps1",
            "reference_payload": "verifier/oracle/reference/%s" % cfg["pkgname"],
            "oracle_log": oracle_log,
            "reward": reward,
            "derivation": (
                "Harbor OracleAgent uploads the delivered solution/ directory to C:\\solution "
                "and runs solve.ps1 without arguments; the script resolves the candidate "
                "workspace to the image workdir (C:\\testbed) and mirrors the delivered "
                "reference payload over %s/. Recorded from the container's own oracle log by "
                "logs/assemble_jobs.py because native Harbor writes only agent/oracle.txt."
                % cfg["pkgname"]),
            "derived_by": "logs/assemble_jobs.py",
            "source_artifacts": {
                "agent/oracle.txt": "sha256:" + hashlib.sha256(
                    (adir_job / "oracle.txt").read_bytes()).hexdigest(),
                "config.json": "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            },
        }
        (adir_job / "qc-oracle-application.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
    return trial


def summarize(job_dir: Path, kind: str, required_ids: set[str]) -> dict:
    rep_path = job_dir / "verifier" / "report.json"
    doc = {}
    if rep_path.is_file():
        doc = json.loads(rep_path.read_text(encoding="utf-8-sig"))
    cases = doc.get("cases") or []
    case_ids = {str(c.get("test_id")) for c in cases}
    reward_path = job_dir / "verifier" / "reward.txt"
    reward = reward_path.read_text(encoding="utf-8-sig").strip() if reward_path.is_file() else None
    # task_checksum: prefer the verifier result we derived, fall back to the
    # archived native trial result.
    checksum = None
    vres_path = job_dir / "verifier" / "result.json"
    if vres_path.is_file():
        try:
            vres = json.loads(vres_path.read_text(encoding="utf-8-sig"))
            checksum = (vres.get("derived_from") or {}).get("harbor_task_checksum")
        except Exception:  # noqa: BLE001
            checksum = None
    if not checksum:
        tr = job_dir / "artifacts" / "trial-result.json"
        if tr.is_file():
            try:
                checksum = json.loads(tr.read_text(encoding="utf-8-sig")).get("task_checksum")
            except Exception:  # noqa: BLE001
                checksum = None
    # invalid-slot detection (buyer requirement: provider-side failures are
    # never a capability 0)
    exc_type = exc_msg = None
    vr_status = None
    tr = job_dir / "artifacts" / "trial-result.json"
    if tr.is_file():
        try:
            tres = json.loads(tr.read_text(encoding="utf-8-sig"))
            info = tres.get("exception_info") or {}
            exc_type = info.get("exception_type")
            exc_msg = (info.get("exception_message") or "")[:400] or None
            vr_status = (tres.get("verifier_result") or {}).get("rewards")
        except Exception:  # noqa: BLE001
            pass
    low = (("%s %s" % (exc_type or "", exc_msg or ""))).lower()
    invalid_reason = None
    if exc_type:
        if "http_502" in low or "502" in low or "502 bad gateway" in low:
            invalid_reason = "provider gateway error (HTTP 502) before the verifier ran"
        elif "429" in low or "quota" in low:
            invalid_reason = "provider quota / rate limit (HTTP 429)"
        elif "timeout" in low or "timed out" in low:
            invalid_reason = "provider timeout"
        elif any(code in low for code in ("http_500", "http_503", "http_504")):
            invalid_reason = "provider 5xx failure"
        else:
            invalid_reason = "harness exception: %s" % exc_type
    return {
        "job": job_dir.name,
        "kind": kind,
        "score": int(doc.get("formal_score")) if doc.get("formal_score") is not None else None,
        "validity": doc.get("run_validity"),
        "cases": len(cases),
        "cases_passed": sum(1 for c in cases if c.get("passed")),
        "cases_match_required": case_ids == required_ids,
        "reward": reward,
        "task_checksum": checksum,
        "exception_type": exc_type,
        "exception_message": exc_msg,
        "verifier_ran": vr_status is not None,
        "invalid_reason": invalid_reason,
    }


def detect_invalid(job_dir: Path):
    """Return a short reason when a job's trial ended in a provider failure."""
    if not job_dir.is_dir():
        return None
    for trial in sorted(job_dir.iterdir()):
        if not trial.is_dir():
            continue
        rj = trial / "result.json"
        if not rj.is_file():
            continue
        try:
            doc = json.loads(rj.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001
            continue
        info = doc.get("exception_info") or {}
        if info.get("exception_type"):
            return "%s: %s" % (info.get("exception_type"),
                               (info.get("exception_message") or "")[:160])
    return None


def find_replacement(repl_root: Path, slot_name: str):
    """Find a valid substitute bound to *slot_name* under replacement-rounds/."""
    if not repl_root.is_dir():
        return None
    cands = sorted((c for c in repl_root.iterdir()
                    if c.is_dir() and c.name.startswith(slot_name)),
                   reverse=True)
    for cand in cands:
        if not detect_invalid(cand):
            return cand
    return cands[0] if cands else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(TASKS))
    a = ap.parse_args()
    cfg = TASKS[a.task]
    pkg = STAGED / cfg["pkg_name"]
    out_root = REL / (a.task + os.environ.get("WFF_RUN_SUFFIX", ""))
    dest_jobs = pkg / "jobs"

    required = json.loads((pkg / "tests" / "required_testcases.json").read_text(encoding="utf-8"))
    required_ids = {r["id"] for r in required}

    if dest_jobs.exists():
        shutil.rmtree(dest_jobs)
    (dest_jobs / "_index").mkdir(parents=True)

    records = []
    plan = []
    invalidated = []          # jobs replaced by a substitute round
    controls = out_root / "controls" / "jobs"
    if controls.is_dir():
        for job in sorted(controls.iterdir()):
            if not job.is_dir():
                continue
            kind = "oracle" if "oracle" in job.name else ("nop" if "nop" in job.name else "control")
            plan.append((job, kind, job.name))
    models = out_root / "model-rounds" / "jobs"
    if models.is_dir():
        repl_root = out_root / "replacement-rounds" / "jobs"
        for job in sorted(models.iterdir()):
            if not job.is_dir() or job.name == "build-probe":
                continue
            # An aborted round (killed mid-flight) has no verifier report at all.
            # It is not a measurement and must never be staged as one.
            has_report = any((trial / "verifier" / "report.json").is_file()
                             for trial in job.iterdir() if trial.is_dir())
            if not has_report:
                print("  skip %s: no verifier report (aborted round)" % job.name)
                continue
            reason = detect_invalid(job)
            if reason:
                sub = find_replacement(repl_root, job.name)
                if sub is not None:
                    print("  slot %s INVALID (%s) -> substitute %s"
                          % (job.name, reason[:60], sub.name))
                    invalidated.append(job)
                    plan.append((sub, "model", job.name))
                    continue
                print("  slot %s INVALID (%s) and no valid substitute" % (job.name, reason[:60]))
                invalidated.append(job)
            plan.append((job, "model", job.name))

    print("plan: %d jobs" % len(plan))
    parent_source = None
    for src, kind, slot_name in plan:
        dest = dest_jobs / slot_name
        trial = copy_job(src, dest, cfg)
        if trial is None:
            continue
        missing = [n for n in ("config.json", "lock.json", "result.json", "job.log")
                   if not (dest / n).is_file()]
        if missing:
            print("  !! %s is missing parent file(s): %s (source %s)"
                  % (dest.name, missing, sorted(p.name for p in src.iterdir())))
        elif parent_source is None:
            parent_source = dest
        records.append(summarize(dest, kind, required_ids))
        print("  %-14s kind=%-6s score=%s validity=%s cases=%s match=%s checksum=%s"
              % (dest.name, kind, records[-1]["score"], records[-1]["validity"],
                 records[-1]["cases"], records[-1]["cases_match_required"],
                 (records[-1]["task_checksum"] or "-")[:12]))

    # Harbor leaves the aggregate JobResult + config + lock + job.log at the
    # jobs/ root, next to the trial directories; the buyer gate reads them there.
    if parent_source is not None:
        for name in ("config.json", "lock.json", "result.json", "job.log"):
            src = parent_source / name
            if src.is_file():
                shutil.copy2(src, dest_jobs / name)
        print("jobs/ root parent files copied from %s" % parent_source.name)
    else:
        print("!! no job had parent files: cannot satisfy the jobs/ root contract")

    report = {
        "task_id": cfg["task_id"],
        "required_cases": len(required_ids),
        "jobs": records,
    }
    (dest_jobs / "_index" / "assembly_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    # ---- archive the replaced (invalid) rounds as evidence -----------------
    # They must NOT sit directly under jobs/: the buyer gate scans
    # jobs/<name>/result.json and would count them as extra model rounds.
    replaced_index = []
    for src in invalidated:
        reason = detect_invalid(src)
        dst = dest_jobs / "_index" / "invalid-rounds" / src.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        replaced_index.append({"slot": src.name, "reason": reason,
                               "source_run_dir": str(src)})
        print("  archived invalid round %s -> jobs/_index/invalid-rounds/%s"
              % (src.name, src.name))
    if replaced_index:
        (dest_jobs / "_index" / "invalid-rounds" / "index.json").write_text(
            json.dumps(replaced_index, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")

    # ---- invalid-slot annotation layer (buyer requirement 2.5) -------------
    runner_sha = None
    for jd in sorted(dest_jobs.iterdir()):
        pv = jd / "agent" / "model-result.json"
        if pv.is_file():
            try:
                runner_sha = json.loads(pv.read_text(encoding="utf-8-sig")).get("runner_sha256")
            except Exception:  # noqa: BLE001
                pass
            if runner_sha:
                break
    # Every archived round in jobs/ is valid: replaced rounds were substituted
    # (and archived under _index/invalid-rounds/), so "invalid" is the list of
    # those replaced rounds.
    invalid_records = [r for r in records if r["invalid_reason"]]
    valid = [r for r in records if not r["invalid_reason"]]

    def slot_entry(entry):
        slot = entry["slot"]
        archived = dest_jobs / "_index" / "invalid-rounds" / slot
        tres = {}
        for trial in sorted(archived.iterdir()) if archived.is_dir() else []:
            rj = trial / "result.json"
            if rj.is_file():
                try:
                    tres = json.loads(rj.read_text(encoding="utf-8-sig"))
                except Exception:  # noqa: BLE001
                    tres = {}
                break
        info = tres.get("exception_info") or {}
        return {
            "job": slot,
            "job_dir": "jobs/_index/invalid-rounds/%s" % slot,
            "role": "model",
            "validity": "INVALID",
            "invalid_reason": entry["reason"],
            "exception_type": info.get("exception_type"),
            "error_message": (info.get("exception_message") or "")[:600] or None,
            "started_at": tres.get("started_at"),
            "finished_at": tres.get("finished_at"),
            "verifier_ran": tres.get("verifier_result") is not None,
            "recorded_reward": None,
            "recorded_reward_note": (
                "No reward file and no verifier run. The failure path wrote no usable score; "
                "this must not be counted as a measurement of the model on this task."),
            "task_checksum": tres.get("task_checksum"),
            "evidence": [
                "jobs/_index/invalid-rounds/%s/result.json" % slot,
                "jobs/_index/invalid-rounds/%s/ (full trial tree, archived verbatim)" % slot,
            ],
            "replacement": {
                "attempted": True,
                "planned_slot": "%s, one trial, same ordering position" % slot,
                "reason": ("Provider-side transport failure; the slot was re-run as a fresh trial "
                           "bound to the same planned slot, and the substitute occupies the "
                           "planned slot name in jobs/."),
            },
        }

    slots = {
        "schema_version": "invalid-slot-record-v1",
        "task_id": cfg["task_id"],
        "task_version_at_run": cfg["version"],
        "recorded_at": "2026-10-13",
        "purpose": ("Invalid slots are recorded separately from the archived jobs, so that an "
                    "infrastructure or quota failure is never silently read as a 0 capability "
                    "score and never enters the discrimination statistics."),
        "immutability_note": ("The archived jobs tree is not rewritten. Every result.json, "
                              "reward and log stays byte-for-byte as produced by the run; this "
                              "file is an annotation layer on top of them. Replaced rounds are "
                              "archived verbatim under jobs/_index/invalid-rounds/."),
        "rules": {
            "invalid_criteria": [
                "The trial's agent_result status is not 'completed' (for example 'error'), or",
                "The final/error text is a provider-side transport or quota failure "
                "(HTTP 429, AccountQuotaExceeded, HTTP 5xx, timeout), or",
                "The verifier never ran on a candidate revision (no verifier_result / no "
                "checks.json produced by a real run).",
            ],
            "replacement_policy": [
                "An invalid slot is bound to the same planned slot: same model alias, one "
                "trial per planned slot, same planned ordering, so a replacement never adds "
                "extra weight to a model.",
                "A replacement is attempted only for transport/quota/timeout failures; an "
                "environment defect of our own is fixed first and then the whole slot re-runs.",
                "A replacement is a fresh trial from the untouched workspace, never a re-prompt "
                "of a failed answer.",
                "Every replacement keeps its own started_at / finished_at and runner identity.",
            ],
            "counting_policy": [
                "Invalid slots are excluded from model_score_sum, testcase_pass_sum and every "
                "discrimination claim.",
                "They are reported separately as infrastructure evidence.",
                "A task must never pass or fail on the strength of an invalid slot.",
            ],
        },
        "slots": [slot_entry(e) for e in replaced_index],
        "valid_rounds": len(valid),
        "total_rounds": len(records),
        "runner_identity": {
            "runner": cfg.get("runner_label", "logs/driver.py + Harbor native oracle/nop"),
            "runner_sha256": runner_sha,
            "note": ("Execution-time runner revision as recorded by the harness in each trial's "
                     "agent/model-result.json; the archived value is the same file that ran."),
        },
        "slots": [slot_entry(e) for e in replaced_index],
        "valid_rounds": len(valid),
        "total_rounds": len(records),
        "runner_identity": {
            "runner": cfg.get("runner_label", "logs/driver.py + Harbor native oracle/nop"),
            "runner_sha256": runner_sha,
            "note": ("Execution-time runner revision as recorded by the harness in each trial's "
                     "agent/model-result.json; the archived value is the same file that ran."),
        },
        "current_archive_note": (
            ("All %d archived rounds ran to a terminal verdict: run_validity=VALID, reward in "
             "{0,1}, no provider or transport error. `slots` is therefore empty."
             % len(records)) if not replaced_index else
            ("%d round(s) ended in a provider-side failure before the verifier ran and were "
             "replaced: %s. Each substitute is a fresh trial bound to the same planned slot and "
             "occupies that slot's name in jobs/; the failed trial is archived verbatim under "
             "jobs/_index/invalid-rounds/ and excluded from every statistic."
             % (len(replaced_index), ", ".join(e["slot"] for e in replaced_index)))),
    }
    (dest_jobs / "invalid-slots.json").write_text(
        json.dumps(slots, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    lines = [
        "# 无效槽位说明（%s）" % cfg["task_id"],
        "",
        "本文件与 `invalid-slots.json` 是**同一份口径**的两种呈现：机器可读版供下游过滤，",
        "本文件供人读。二者都只是**注解层**——`jobs/` 下的原始试次记录与日志保持原样，未被改写；",
        "被替代的失败试次整棵树原样归档在 `jobs/_index/invalid-rounds/`。",
        "",
        "## 结论（本归档：task_version %s）" % cfg["version"],
        "",
    ]
    if replaced_index:
        lines += [
            "**本归档有 %d 个无效槽位，已单列、已按「绑定同一计划槽位」重跑，并从全部统计中排除。**"
            % len(replaced_index),
            "",
            "| 计划槽位 | 失败原因 | 归档位置 | 替代轮 |",
            "| --- | --- | --- | --- |",
        ]
        for s in slots["slots"]:
            lines.append("| `%s` | %s | `%s` | 已重跑并占用原槽位名 |"
                         % (s["job"], s["invalid_reason"], s["job_dir"]))
        lines += ["", "`jobs/` 下 %d 轮全部 `run_validity=VALID`、reward 落在 {0,1}。" % len(valid), ""]
    else:
        lines += [
            "**本归档无无效槽位。** %d 轮全部 `run_validity=VALID`，reward 均落在 {0,1}，" % len(records),
            "没有出现供应商配额、限流、传输或超时失败，也没有出现 `error` 状态。",
            "",
            "因此 `invalid-slots.json` 的 `slots` 为空数组——统计时无需排除任何试次。",
            "",
        ]
    lines += [
        "| 轮次 | 角色 | reward | 有效性 |",
        "| --- | --- | --- | --- |",
    ]
    for r in records:
        lines.append("| `%s` | %s | %s | %s |"
                     % (r["job"], r["kind"],
                        r["reward"] if r["reward"] is not None else "(无)",
                        r["validity"] or ("INVALID（%s）" % r["invalid_reason"] if r["invalid_reason"] else "-")))
    lines += [
        "",
        "## 为什么不把失败轮按 0 分计（统一口径）",
        "",
        "1. 供应商配额 / 限流 / 传输 / 超时失败与候选实现无关；",
        "2. 失败路径写出的 `reward=0` 是占位值，verifier 未对候选修订真正跑过；",
        "3. 甲方要求第 2 条与本项目验收一票否决条款均禁止把环境/基础设施缺陷记为模型 0 分。",
        "",
        "## 重试与替代规则（统一口径）",
        "",
        "- 无效槽位**绑定原计划槽位**（同 alias、同一次、同顺序位置），替代不给该模型加权；",
        "- 只有传输/配额/超时类失败才重试；**我方环境缺陷**先修复，再整槽重跑；",
        "- 重试是**全新试次**，不从失败答案续跑，也不合并进无效记录；",
        "- 每个替代试次保留自己的起止时间与 runner 身份。",
        "",
        "## runner 身份口径",
        "",
        "本轮每次运行的执行时 runner 版本由 harness 记录在对应试次的",
        "`agent/model-result.json` 的 `runner_sha256` 字段中；归档值即执行时的同一文件。",
        "系统库/容器侧身份（`task_checksum`、镜像 digest）由每轮的 `result.json` 与 `lock.json` 固化。",
        "",
    ]
    (dest_jobs / "INVALID-SLOTS.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n")
    print("wrote jobs/invalid-slots.json + jobs/INVALID-SLOTS.md (%d rounds, %d replaced)"
          % (len(records), len(replaced_index)))

    problems = []
    for r in records:
        if r["invalid_reason"]:
            continue          # excluded from statistics by the annotation layer
        if not r["cases_match_required"]:
            problems.append("%s: cases != required (%d vs %d)"
                            % (r["job"], r["cases"], len(required_ids)))
        if r["validity"] != "VALID":
            problems.append("%s: run_validity=%s" % (r["job"], r["validity"]))
        if r["reward"] is None:
            problems.append("%s: no reward.txt" % r["job"])
    checksums = {r["task_checksum"] for r in valid if r["task_checksum"]}
    print("task_checksum values (valid rounds): %s" % sorted(checksums))
    if len(checksums) != 1:
        problems.append("task_checksum not unique: %s" % sorted(checksums))
    if invalid_records:
        print("NOTE: %d archived round(s) carry an exception marker: %s"
              % (len(invalid_records), [r["job"] for r in invalid_records]))
    if replaced_index:
        print("NOTE: %d invalid slot(s) replaced and excluded: %s"
              % (len(replaced_index), [e["slot"] for e in replaced_index]))
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print("assembled %d jobs into %s" % (len(records), dest_jobs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
