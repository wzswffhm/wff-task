# -*- coding: utf-8 -*-
"""assemble_wpeimg_harbor_jobs.py —— 把 Harbor 原生 trial 目录组装成交付包 jobs/。

新版自检（validate_model_jobs.py）要求交付包 jobs/ 下**恰好 14 个** job 目录，
每个目录里含：

    config.json  lock.json  result.json  trial.log
    artifacts/manifest.json
    agent/model-result.json + agent/trajectory.jsonl        (模型轮)
    agent/oracle.txt + agent/qc-oracle-application.json     (Oracle 轮)
    verifier/result.json  verifier/reward.txt
    verifier/test-stdout.txt  verifier/verifier.log

Harbor 原生产物已经是这个形状的绝大部分，缺的三样由本脚本**从原生产物派生**
（不新造执行、不改分数）：

  * verifier/result.json —— 由 verifier/report.json（题包 aggregate-v1）转成
    {status, score, testcases:[{test_id, outcome}]}，供自检逐项比对；
  * verifier/verifier.log —— 判分链路日志（取自 test-stdout.txt）；
  * agent/qc-oracle-application.json —— Oracle 轮参考解注入说明。

用法：
    python assemble_wpeimg_harbor_jobs.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = ROOT / "harbor-windows" / "wfflab__wpeimg-219-v1.0.0-delivery"
BUILD = ROOT / "harbor-windows" / "_qc_runs" / "wpeimg-build"
CONTROL_JOBS = BUILD / "qc-controls1" / "jobs"
MODEL_JOBS = BUILD / "model-rounds" / "jobs"
JOBS_OUT = PKG / "jobs"
REQUIRED = PKG / "tests" / "required_testcases.json"


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


def find_trials(jobs_dir: Path) -> list[tuple[str, Path]]:
    """返回 [(job_name, trial_dir)]。"""
    out = []
    if not jobs_dir.is_dir():
        return out
    for job in sorted(jobs_dir.iterdir()):
        if not job.is_dir():
            continue
        for trial in sorted(job.iterdir()):
            if trial.is_dir() and (trial / "result.json").is_file():
                out.append((job.name, trial))
    return out


def outcomes(report: dict) -> dict:
    """aggregate-v1 report.json -> {test_id: PASS/FAIL}"""
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


def patch_trial(dst: Path, kind: str, required_ids: set[str]) -> dict:
    """补齐自检要求的派生文件，返回一条报告。"""
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

    # 1) verifier/result.json（自检读的是这个文件）
    result = {
        "schema_version": "harbor-jobs-verifier-v1",
        "status": validity,
        "score": score,
        "task_id": rep.get("task_id"),
        "task_version": rep.get("task_version"),
        "total": rep.get("total"),
        "passed": rep.get("passed"),
        "failed": rep.get("failed"),
        "testcases": [{"test_id": k, "outcome": v} for k, v in sorted(cases.items())],
        "source": "derived from verifier/report.json (aggregate-v1) by assemble_wpeimg_harbor_jobs.py",
    }
    write_json(ver / "result.json", result)

    # 2) verifier/verifier.log —— 判分链路的原始输出
    stdout = (ver / "test-stdout.txt")
    body = stdout.read_text(encoding="utf-8", errors="replace") if stdout.is_file() else ""
    (ver / "verifier.log").write_text(
        "verifier: tests/test.ps1 -> run_tests.ps1 + aggregate_results.ps1\n"
        "harbor_trial: %s\nreward: %s\n--- raw stdout ---\n%s"
        % (dst.name, score, body), encoding="utf-8", newline="\n")

    # 3) Oracle 轮的参考解注入说明
    if kind == "oracle":
        agent = dst / "agent"
        agent.mkdir(parents=True, exist_ok=True)
        oracle_txt = agent / "oracle.txt"
        note = {
            "agent": "oracle",
            "solution_entry": "solution/solve.ps1",
            "reference_payload": "solution/reference/wpeimg",
            "oracle_log": oracle_txt.read_text(encoding="utf-8", errors="replace")
            if oracle_txt.is_file() else "",
            "reward": score,
            "derivation": ("Harbor OracleAgent uploads solution/ to C:\\solution and runs "
                           "solve.ps1 without arguments; the script resolves the candidate "
                           "workspace to the image workdir (C:\\testbed) and mirrors the "
                           "delivered reference payload over wpeimg/."),
            "derived_by": "assemble_wpeimg_harbor_jobs.py",
        }
        write_json(agent / "qc-oracle-application.json", note)

    return {"trial": dst.name, "kind": kind, "score": score, "validity": validity,
            "cases": len(cases),
            "cases_match_required": set(cases) == required_ids}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    required = read_json(REQUIRED, []) or []
    required_ids = {r["id"] for r in required if isinstance(r, dict) and r.get("id")}

    trials = ([(name, path, "oracle" if "-oracle-" in name else "nop")
               for name, path in find_trials(CONTROL_JOBS)]
              + [(name, path, "model") for name, path in find_trials(MODEL_JOBS)])
    print("发现 trial：控制轮 %d + 模型轮 %d = %d"
          % (len(find_trials(CONTROL_JOBS)), len(find_trials(MODEL_JOBS)), len(trials)))
    if a.dry_run:
        for name, path, kind in trials:
            print("  %-8s %-46s %s" % (kind, path.name, name))
        return 0

    if JOBS_OUT.exists():
        shutil.rmtree(JOBS_OUT)
    JOBS_OUT.mkdir(parents=True)

    report = []
    for job_name, trial, kind in trials:
        dst = JOBS_OUT / trial.name
        shutil.copytree(trial, dst)
        report.append(patch_trial(dst, kind, required_ids))

    # jobs/ 父级的四个 Harbor job 文件（取自任一 job 的原生文件）
    sample = next((p for p in sorted(CONTROL_JOBS.iterdir()) if p.is_dir()), None)
    if sample is not None:
        for fn in ("config.json", "lock.json", "result.json", "job.log"):
            src = sample / fn
            if src.is_file():
                shutil.copy2(src, JOBS_OUT / fn)
    write_json(JOBS_OUT / "_index" / "assembly_report.json",
               {"trials": report,
                "n_trials": len(report),
                "required_testcases": len(required_ids),
                "source_control_jobs": str(CONTROL_JOBS),
                "source_model_jobs": str(MODEL_JOBS),
                "derived_files": ["verifier/result.json", "verifier/verifier.log",
                                  "agent/qc-oracle-application.json (oracle only)"]})
    ok = sum(1 for r in report if r["score"] in (0, 1) and r["cases_match_required"])
    print("组装完成：%d 个 job，其中 %d 个分数合法且 testcase 集合匹配" % (len(report), ok))
    for r in report:
        flag = "OK " if (r["score"] in (0, 1) and r["cases_match_required"]) else "!! "
        print("  %s%-46s kind=%-7s score=%s validity=%s cases=%s"
              % (flag, r["trial"], r["kind"], r["score"], r["validity"], r["cases"]))
    return 0 if ok == len(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
