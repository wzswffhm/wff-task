# -*- coding: utf-8 -*-
"""assemble_wciocp_harbor_jobs.py —— 把 Harbor 原生 trial 组装成交付包 jobs/。

交付形态与同批已交付包（219）一致：jobs/ 下每个 job 一个目录，目录里是
job 级四文件（config.json / lock.json / result.json / job.log）加上从该 job
唯一 trial 平铺上来的 agent/ 、artifacts/ 、verifier/ 、trial.log。

自检（validate_model_jobs.py / inspect_delivery.py）逐项读取：
    verifier/result.json  —— 判分结果的逐 testcase 形态
    verifier/reward.txt   —— Harbor 的正式分（0/1）
    verifier/test-stdout.txt
    agent/trajectory.jsonl（模型轮）/ agent/oracle.txt（Oracle 轮）

其中 verifier/result.json 与 verifier/verifier.log 由本脚本**从原生产物派生**，
不新造执行、不改分数。

用法：
    python assemble_wciocp_harbor_jobs.py [--dry-run] [--allow-failed]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = ROOT / "harbor-windows" / "wfflab__wciocp-220-v1.0.0-delivery"
BUILD = ROOT / "harbor-windows" / "_qc_runs" / "wciocp-build"
CONTROL_JOBS = BUILD / "controls" / "jobs"
MODEL_JOBS = BUILD / "model-rounds" / "jobs"
JOBS_OUT = PKG / "jobs"
REQUIRED = PKG / "tests" / "required_testcases.json"

JOB_LEVEL_FILES = ("config.json", "lock.json", "result.json", "job.log")
TRIAL_LEVEL_DIRS = ("agent", "artifacts", "verifier")
# The trial copy of result.json carries task_checksum, trial_name and the verifier
# reward; the job-level summary does not. It therefore has to win over the
# job-level file with the same name. config.json / lock.json are trial-scoped too.
TRIAL_LEVEL_FILES = ("config.json", "lock.json", "result.json", "trial.log", "exception.txt")


def read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8", newline="\n")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def find_trials(jobs_dir: Path):
    """返回 [(job_name, trial_dir)]，一个 job 最多一个 trial。"""
    out = []
    if not jobs_dir.is_dir():
        return out
    for job in sorted(jobs_dir.iterdir()):
        if not job.is_dir():
            continue
        trials = [d for d in sorted(job.iterdir())
                  if d.is_dir() and (d / "result.json").is_file()]
        if trials:
            out.append((job.name, trials[0]))
    return out


def outcomes(report: dict) -> dict:
    res = {}
    for c in report.get("cases") or []:
        tid = c.get("test_id")
        if not tid:
            continue
        passed = c.get("passed")
        if isinstance(passed, bool):
            res[tid] = "PASS" if passed else "FAIL"
        else:
            res[tid] = str(c.get("outcome") or c.get("status") or "").upper()
    return res


def flatten(job_dir: Path, trial_dir: Path) -> None:
    """把 trial 内容平铺进 job 目录，保留 job 级四文件。"""
    for name in TRIAL_LEVEL_DIRS:
        src = trial_dir / name
        if not src.is_dir():
            continue
        dst = job_dir / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    for name in TRIAL_LEVEL_FILES:
        src = trial_dir / name
        if src.is_file():
            shutil.copy2(src, job_dir / name)


def patch_trial(dst: Path, kind: str, required_ids: set) -> dict:
    ver = dst / "verifier"
    rep = read_json(ver / "report.json", {}) or {}
    score = None
    rtxt = ver / "reward.txt"
    if rtxt.is_file():
        try:
            score = int(float(rtxt.read_text(encoding="utf-8-sig").strip()))
        except Exception:
            score = None
    cases = outcomes(rep)
    validity = rep.get("run_validity") or ("VALID" if score in (0, 1) else None)

    result = {
        "schema_version": "harbor-jobs-verifier-v1",
        "status": validity,
        "score": score,
        "task_id": rep.get("task_id"),
        "task_version": rep.get("task_version"),
        "total": rep.get("total"),
        "passed": rep.get("passed"),
        "failed": rep.get("failed"),
        "invalid": rep.get("invalid"),
        "formal_score": rep.get("formal_score"),
        "testcases": [{"test_id": k, "outcome": v} for k, v in sorted(cases.items())],
        "source": "derived from verifier/report.json (aggregate-v1) by assemble_wciocp_harbor_jobs.py",
    }
    write_json(ver / "result.json", result)

    stdout = ver / "test-stdout.txt"
    body = stdout.read_text(encoding="utf-8", errors="replace") if stdout.is_file() else ""
    (ver / "verifier.log").write_text(
        "verifier: tests/test.ps1 -> run_tests.ps1 + aggregate_results.ps1\n"
        "harbor_trial: %s\nreward: %s\n--- raw stdout ---\n%s"
        % (dst.name, score, body), encoding="utf-8", newline="\n")

    if kind == "oracle":
        agent = dst / "agent"
        agent.mkdir(parents=True, exist_ok=True)
        oracle_txt = agent / "oracle.txt"
        note = {
            "agent": "oracle",
            "solution_entry": "solution/solve.ps1",
            "reference_payload": "verifier/oracle/reference/wciocp",
            "oracle_log": oracle_txt.read_text(encoding="utf-8", errors="replace")
            if oracle_txt.is_file() else "",
            "reward": score,
            "derivation": ("Harbor's oracle agent uploads solution/ and runs solve.ps1; "
                           "the script resolves the reference payload from "
                           "C:\\solution\\reference\\wciocp or the injected "
                           "wciocp_REFERENCE_ROOT and mirrors it over wciocp/."),
            "derived_by": "assemble_wciocp_harbor_jobs.py",
        }
        write_json(agent / "qc-oracle-application.json", note)

    return {"trial": dst.name, "kind": kind, "score": score, "validity": validity,
            "cases": len(cases), "cases_match_required": set(cases) == required_ids}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-failed", action="store_true",
                    help="把失败的 trial 也归档（默认拒绝）")
    a = ap.parse_args()

    required = read_json(REQUIRED, {}) or {}
    rows = required.get("testcases") if isinstance(required, dict) else required
    required_ids = {r["id"] for r in (rows or []) if isinstance(r, dict) and r.get("id")}

    trials = ([(name, path, "oracle" if "-oracle-" in name else "nop")
               for name, path in find_trials(CONTROL_JOBS)]
              + [(name, path, "model") for name, path in find_trials(MODEL_JOBS)])
    print("发现 trial：控制轮 %d + 模型轮 %d = %d"
          % (len(find_trials(CONTROL_JOBS)), len(find_trials(MODEL_JOBS)), len(trials)))
    if a.dry_run:
        for name, path, kind in trials:
            print("  %-7s job=%-16s trial=%s" % (kind, name, path.name))
        return 0

    if JOBS_OUT.exists():
        shutil.rmtree(JOBS_OUT)
    JOBS_OUT.mkdir(parents=True)

    report = []
    for job_name, trial, kind in trials:
        dst = JOBS_OUT / job_name
        dst.mkdir(parents=True)
        job_dir = trial.parent
        for fn in JOB_LEVEL_FILES:
            src = job_dir / fn
            if src.is_file():
                shutil.copy2(src, dst / fn)
        flatten(dst, trial)
        entry = patch_trial(dst, kind, required_ids)
        entry["job"] = job_name
        report.append(entry)

    sample = next((p for p in sorted(CONTROL_JOBS.iterdir()) if p.is_dir()), None)
    if sample is not None:
        for fn in JOB_LEVEL_FILES:
            src = sample / fn
            if src.is_file():
                shutil.copy2(src, JOBS_OUT / fn)

    checksums = set()
    for job_dir in sorted(JOBS_OUT.iterdir()):
        if not job_dir.is_dir():
            continue
        rj = read_json(job_dir / "result.json", {}) or {}
        if rj.get("task_checksum"):
            checksums.add(rj["task_checksum"])

    write_json(JOBS_OUT / "_index" / "assembly_report.json",
               {"trials": report,
                "n_trials": len(report),
                "required_testcases": len(required_ids),
                "harbor_task_checksums": sorted(checksums),
                "source_control_jobs": str(CONTROL_JOBS),
                "source_model_jobs": str(MODEL_JOBS),
                "derived_files": ["verifier/result.json", "verifier/verifier.log",
                                  "agent/qc-oracle-application.json (oracle only)"]})

    ok = sum(1 for r in report if r["score"] in (0, 1) and r["cases_match_required"])
    print("组装完成：%d 个 job，其中 %d 个分数合法且 testcase 集合匹配" % (len(report), ok))
    for r in report:
        good = r["score"] in (0, 1) and r["cases_match_required"]
        print("  %s%-16s kind=%-7s score=%s validity=%s cases=%s"
              % ("OK " if good else "!! ", r["job"], r["kind"], r["score"],
                 r["validity"], r["cases"]))
    if len(checksums) > 1:
        print("!! 各 job 的 task checksum 不一致：%s" % sorted(checksums))
    if not a.allow_failed and ok != len(report):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
