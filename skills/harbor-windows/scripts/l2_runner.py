# -*- coding: utf-8 -*-
"""l2_runner.py —— harbor-windows 本机 L2 判分器

复现 tests/test.ps1 的判分链路（沙箱化，不依赖 Docker）：
    复制 environment/workspace → 沙箱
    → git 基线提交
    → 应用候选补丁（no-change 传 None）
    → git apply tests/test_patch.diff（隐藏测试）
    → 环境预检 import pytest, <pkg>
    → pytest --json-report
    → python grade.py <log> <logs>
    → 汇总 summary.json

用法：
    python l2_runner.py --task <题包目录> --case <名称> [--patch <补丁文件>] [--out <根>]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PY = r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
GIT = "git"
DEF_OUT = r"C:\Users\Administrator\AppData\Local\Temp\wff-l2\runs"


def sh(args, cwd, timeout=1800, env=None):
    p = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, env=env)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def git(args, cwd):
    return sh([GIT,
               "-c", "core.autocrlf=false",
               "-c", "core.longpaths=true",
               "-c", "user.name=wfflab",
               "-c", "user.email=wfflab@local",
               "-c", "commit.gpgsign=false"] + args, cwd)


def run_case(task_dir: Path, case: str, patch: Path | None, out_root: Path) -> dict:
    sandbox = out_root / case
    tests_dir = out_root / (case + "__tests")

    def _clean(p: Path):
        for _ in range(3):
            if not p.exists():
                return True
            try:
                shutil.rmtree(p)
            except Exception:
                subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(p)],
                               capture_output=True, text=True)
            time.sleep(0.3)
        return not p.exists()

    _clean(sandbox)
    _clean(tests_dir)

    summary = {"case": case, "status": "INVALID", "score": None,
               "pytest_rc": None, "grade_rc": None,
               "f2p_all_pass": None, "p2p_all_pass": None,
               "infrastructure_valid": None, "candidate_failure": None,
               "patch": str(patch) if patch else None,
               "invalid_reason": None, "seed": None, "patch_applied": None,
               "pytest_passed": None, "pytest_total": None}

    # ---------- 1. 准备沙箱 ----------
    workspace = task_dir / "environment" / "workspace"
    if not workspace.is_dir():
        summary["invalid_reason"] = "workspace_missing"
        return summary
    shutil.copytree(workspace, sandbox, dirs_exist_ok=True)

    src_tests = task_dir / "tests"
    shutil.copytree(src_tests, tests_dir, dirs_exist_ok=True)

    # ---------- 2. git 基线 ----------
    rc, o, e = git(["init", "-q"], sandbox)
    if rc != 0:
        summary["invalid_reason"] = "git_init_failed: %s" % (e or o)[:200]
        return summary
    git(["add", "-A"], sandbox)
    rc, o, e = git(["commit", "-q", "-m", "base"], sandbox)
    if rc != 0:
        summary["invalid_reason"] = "git_commit_failed: %s" % (e or o)[:200]
        return summary
    rc, base, _ = git(["rev-parse", "HEAD"], sandbox)
    summary["seed"] = base.strip() if rc == 0 else None

    # ---------- 3. 应用候选补丁 ----------
    if patch is not None:
        rc, o, e = git(["apply", "--check", "--binary", "--whitespace=nowarn", str(patch)], sandbox)
        if rc != 0:
            summary["invalid_reason"] = "candidate_patch_check_failed"
            summary["patch_applied"] = False
            (out_root / (case + ".patch-err.txt")).write_text((e or o), encoding="utf-8")
            return summary
        rc, o, e = git(["apply", "--binary", "--whitespace=nowarn", str(patch)], sandbox)
        if rc != 0:
            summary["invalid_reason"] = "candidate_patch_apply_failed"
            summary["patch_applied"] = False
            return summary
    summary["patch_applied"] = True

    # ---------- 4. 应用隐藏测试补丁 ----------
    tp = tests_dir / "test_patch.diff"
    if tp.is_file() and tp.stat().st_size > 0:
        rc, o, e = git(["apply", "--check", "--binary", "--whitespace=nowarn", str(tp)], sandbox)
        if rc != 0:
            summary["invalid_reason"] = "test_patch_check_failed: %s" % (e or o)[:200]
            return summary
        rc, o, e = git(["apply", "--binary", "--whitespace=nowarn", str(tp)], sandbox)
        if rc != 0:
            summary["invalid_reason"] = "test_patch_apply_failed"
            return summary

    # ---------- 5. 环境预检 ----------
    env = dict(os.environ)
    env["PYTHONPATH"] = str(sandbox) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    spec = {}
    spec_path = tests_dir / "swelive_spec.json"
    if spec_path.is_file():
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except Exception:
            spec = {}
    pkgs = spec.get("import_check") or []
    if not pkgs:
        # 从 workspace 顶层包目录推断
        for d in sandbox.iterdir():
            if d.is_dir() and (d / "__init__.py").is_file():
                pkgs = [d.name]
    other = [p for p in pkgs if p]
    rc, o, e = sh([PY, "-c", "import pytest" + ("".join(", %s" % p for p in other))],
                  sandbox, timeout=120, env=env)
    if rc != 0:
        summary["invalid_reason"] = "prepared_environment_missing: %s" % (e or o)[:200]
        return summary

    # ---------- 6. 运行 required 测试 ----------
    reports = sandbox / "reports"
    if reports.exists():
        shutil.rmtree(reports, ignore_errors=True)
    reports.mkdir(parents=True, exist_ok=True)

    # 目标测试文件：优先取 spec 声明的 required 名字所属文件（与 test.ps1 一致）
    test_target = None
    if spec.get("FAIL_TO_PASS") or spec.get("PASS_TO_PASS"):
        ref = (spec.get("FAIL_TO_PASS") or spec.get("PASS_TO_PASS"))[0]
        cand = ref.split("::")[0]
        if (sandbox / cand).is_file():
            test_target = cand
    if test_target is None:
        for f in ("tests/test_windows_fs_semantics.py",):
            if (sandbox / f).is_file():
                test_target = f
    if test_target is None:
        cands = sorted((sandbox / "tests").glob("test_*.py"))
        if cands:
            test_target = "tests/" + cands[-1].name
    if test_target is None:
        summary["invalid_reason"] = "no_test_file"
        return summary

    rc, o, e = sh([PY, "-m", "pytest", "-rA", "--tb=short", "-p", "no:cacheprovider",
                   "--json-report", "--json-report-file=reports/pytest-results.json",
                   test_target],
                  sandbox, timeout=3600, env=env)
    summary["pytest_rc"] = rc
    report_file = sandbox / "reports" / "pytest-results.json"
    if not report_file.is_file():
        summary["invalid_reason"] = "test_report_missing"
        (out_root / (case + ".pytest.log")).write_text((o or "") + (e or ""), encoding="utf-8")
        return summary

    log_txt = report_file.read_text(encoding="utf-8", errors="replace")
    if rc > 1:
        log_txt += "\n===SWELIVE_CANDIDATE_FAILURE compile_or_test_collection_failed===\n"
    log_path = sandbox / "swelive_test.log"
    log_path.write_text(log_txt, encoding="utf-8")
    (out_root / (case + ".pytest.log")).write_text((o or "") + (e or ""), encoding="utf-8")

    try:
        doc = json.loads(log_txt.split("===SWELIVE_CANDIDATE_FAILURE")[0])
        summary["pytest_passed"] = doc.get("summary", {}).get("passed")
        summary["pytest_total"] = doc.get("summary", {}).get("total")
    except Exception:
        pass

    # ---------- 7. 评分 ----------
    logs_root = sandbox / "logs"
    (logs_root / "verifier").mkdir(parents=True, exist_ok=True)
    rc_g, o_g, e_g = sh([PY, str(tests_dir / "grade.py"), str(log_path), str(logs_root)],
                        sandbox, timeout=1800, env=env)
    summary["grade_rc"] = rc_g
    (out_root / (case + ".grade.log")).write_text((o_g or "") + (e_g or ""), encoding="utf-8")

    reward_txt = logs_root / "verifier" / "reward.txt"
    reward_json = logs_root / "verifier" / "reward.json"
    report_json = logs_root / "verifier" / "report.json"

    if not reward_txt.is_file() or not reward_json.is_file():
        summary["invalid_reason"] = "reward_artifact_missing"
        if report_json.is_file():
            rp = json.loads(report_json.read_text(encoding="utf-8"))
            summary["f2p_all_pass"] = rp.get("f2p_all_pass")
            summary["p2p_all_pass"] = rp.get("p2p_all_pass")
            summary["infrastructure_valid"] = rp.get("infrastructure_valid")
            summary["candidate_failure"] = rp.get("candidate_failure")
        return summary

    score = float(reward_txt.read_text(encoding="utf-8").strip())
    if report_json.is_file():
        rp = json.loads(report_json.read_text(encoding="utf-8"))
        summary["f2p_all_pass"] = rp.get("f2p_all_pass")
        summary["p2p_all_pass"] = rp.get("p2p_all_pass")
        summary["infrastructure_valid"] = rp.get("infrastructure_valid")
        summary["candidate_failure"] = rp.get("candidate_failure")
        summary["report"] = rp
    summary["score"] = score
    summary["status"] = "VALID"

    # 归档判分产物（与 0001 evidence 同构）
    for f in ("reward.txt", "reward.json", "reward-details.json", "report.json"):
        src = logs_root / "verifier" / f
        if src.is_file():
            dst = out_root / (case + "__verifier")
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst / f)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, help="题包目录")
    ap.add_argument("--case", required=True, help="用例名")
    ap.add_argument("--patch", help="候选补丁；省略 = no-change")
    ap.add_argument("--out", default=DEF_OUT)
    a = ap.parse_args()

    task_dir = Path(a.task).resolve()
    out_root = Path(a.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    s = run_case(task_dir, a.case, Path(a.patch).resolve() if a.patch else None, out_root)
    s["elapsed"] = round(time.time() - t0, 2)

    (out_root / (a.case + ".summary.json")).write_text(
        json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("[%s] status=%s score=%s pytest_rc=%s grade_rc=%s infr=%s reason=%s (%.1fs)" % (
        a.case, s["status"], s["score"], s["pytest_rc"], s["grade_rc"],
        s["infrastructure_valid"], s["invalid_reason"], s["elapsed"]))
    return 0 if s["status"] == "VALID" else 1


if __name__ == "__main__":
    sys.exit(main())
