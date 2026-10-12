# -*- coding: utf-8 -*-
"""judge_runs.py —— 对 extras/model_runs 下已产出补丁的运行执行判分并回填分数。

判分链路与 l2_runner.py 等价，但适配本题包的 run_tests.ps1 注入式隐藏套件
（本题没有 tests/grade.py，也没有 tests/test_patch.diff）：

    1. 复制 environment/workspace 的内容到判分沙箱
    2. git 基线提交；有 patch.diff 时 git apply（先 --check）
    3. 运行 tests/test.ps1 -TaskRoot <题包> -WorkspaceRoot <沙箱>
       -OutputPath <judge_root>/<case>__verifier/result.json
       隐藏套件经 WLOGSEG_VERIFIER_ROOT 解析
    4. 读 result.json 的 formal_score / cases，回填 run 的
       report.json / per_testcase.json 与 judge/<case>.summary.json

用法：
    python judge_runs.py --task <题包目录> [--models qwen3.8-max-0902]
                         [--runs 1,2,3] [--force]
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

PY = r"C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
PYLIBS = r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\wlogseg-build\pylibs"
VERIFIER_ENV = "WLOGSEG_VERIFIER_ROOT"
GIT = "git"
# 裸名 `powershell` 在子进程的最小 PATH 下解析不到（WinError 2），必须用绝对路径。
PS_DIR = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                      "System32", "WindowsPowerShell", "v1.0")
PS_EXE = os.path.join(PS_DIR, "powershell.exe")


def sh(args, cwd=None, timeout=3600, env=None):
    p = subprocess.run(args, cwd=str(cwd) if cwd else None, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, env=env)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def git(args, cwd):
    return sh([GIT, "-c", "core.autocrlf=false", "-c", "core.longpaths=true",
               "-c", "user.name=wfflab", "-c", "user.email=wfflab@local",
               "-c", "commit.gpgsign=false"] + args, cwd)


def read_json(p: Path, default=None):
    # PowerShell 5.1 的 Out-File -Encoding utf8 会写 BOM，必须用 utf-8-sig 读。
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_dir(p: Path):
    if p.exists():
        shutil.rmtree(p, ignore_errors=True)
    for _ in range(3):
        if not p.exists():
            return True
        time.sleep(0.3)
        shutil.rmtree(p, ignore_errors=True)
    return not p.exists()


def judge_case(task_dir: Path, run_dir: Path, case: str, judge_root: Path) -> dict:
    sandbox = judge_root / case
    vdir = judge_root / (case + "__verifier")
    summary = {"case": case, "status": "INVALID", "score": None,
               "patch": None, "patch_applied": None, "invalid_reason": None,
               "run_validity": None, "total": None, "passed": None, "failed": None,
               "f2p_all_pass": None, "p2p_all_pass": None,
               "evidence_dir": None, "elapsed": None}

    workspace = task_dir / "environment" / "workspace"
    if not workspace.is_dir():
        summary["invalid_reason"] = "workspace_missing"
        return summary

    clean_dir(sandbox)
    clean_dir(vdir)
    shutil.copytree(workspace, sandbox, dirs_exist_ok=True)

    # 包目录必须让 run_tests.ps1 的探测命中
    pkg_probe = sandbox / "wlogseg" / "__init__.py"
    if not pkg_probe.is_file():
        summary["invalid_reason"] = "candidate_package_not_found"
        return summary

    patch = run_dir / "patch.diff"
    if patch.is_file() and patch.stat().st_size > 0:
        summary["patch"] = str(patch)
        git(["init", "-q"], sandbox)
        git(["add", "-A"], sandbox)
        git(["commit", "-q", "-m", "base"], sandbox)
        rc, o, e = git(["apply", "--check", "--binary", "--whitespace=nowarn",
                        str(patch)], sandbox)
        if rc != 0:
            summary["invalid_reason"] = "candidate_patch_check_failed"
            summary["patch_applied"] = False
            (judge_root / (case + ".patch-err.txt")).write_text(
                (e or o), encoding="utf-8")
            return summary
        rc, o, e = git(["apply", "--binary", "--whitespace=nowarn", str(patch)], sandbox)
        if rc != 0:
            summary["invalid_reason"] = "candidate_patch_apply_failed"
            summary["patch_applied"] = False
            return summary
        summary["patch_applied"] = True
    else:
        summary["patch_applied"] = False

    env = dict(os.environ)
    env[VERIFIER_ENV] = str(task_dir / "verifier")
    env["PYTHONPATH"] = PYLIBS + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = os.pathsep.join([os.path.dirname(PY), PS_DIR, env.get("PATH", "")])
    for k in ("PYTHONUTF8", "PYTHONIOENCODING"):
        env.pop(k, None)

    vdir.mkdir(parents=True, exist_ok=True)
    out_json = vdir / "result.json"
    t0 = time.time()
    rc, o, e = sh([PS_EXE, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
                   "-NonInteractive", "-File", str(task_dir / "tests" / "test.ps1"),
                   "-TaskRoot", str(task_dir), "-WorkspaceRoot", str(sandbox),
                   "-OutputPath", str(out_json)], task_dir, timeout=3600, env=env)
    summary["elapsed"] = round(time.time() - t0, 2)
    (vdir / (case + ".stdout.log")).write_text((o or "") + (e or ""), encoding="utf-8")

    doc = read_json(out_json)
    if not isinstance(doc, dict):
        summary["invalid_reason"] = "judge_result_missing"
        return summary

    summary["status"] = "VALID"
    summary["score"] = doc.get("formal_score")
    summary["run_validity"] = doc.get("run_validity")
    summary["total"] = doc.get("total")
    summary["passed"] = doc.get("passed")
    summary["failed"] = doc.get("failed")
    summary["evidence_dir"] = str(vdir.relative_to(task_dir)).replace("\\", "/")
    cases = {c.get("test_id"): bool(c.get("passed")) for c in (doc.get("cases") or [])}
    summary["_cases"] = cases
    summary["f2p_all_pass"] = all(v for k, v in cases.items() if k.startswith("f2p-"))
    summary["p2p_all_pass"] = all(v for k, v in cases.items() if k.startswith("p2p-"))
    # 判分沙箱里的 git init 残留（sandbox/.git）没有任何证据价值，却会让上层仓库
    # 把它当嵌套仓库（gitlink）收走。best-effort 清掉。
    shutil.rmtree(sandbox / ".git", ignore_errors=True)
    return summary


def backfill(task_dir: Path, run_dir: Path, case: str, summary: dict) -> None:
    rep_p = run_dir / "report.json"
    rep = read_json(rep_p, {}) or {}
    pt_p = run_dir / "per_testcase.json"
    pt = read_json(pt_p, {}) or {}
    cases = summary.pop("_cases", {}) or {}

    if summary.get("status") == "VALID":
        rep.update({
            "task_id": "wfflab__wlogseg-218",
            "run_index": rep.get("run_index"),
            "status": "VALID",
            "score": summary.get("score"),
            "judge": {
                "engine": "tests/test.ps1 (本机真实 Windows Runtime，run_tests.ps1 注入式隐藏套件)",
                "run_validity": summary.get("run_validity"),
                "total": summary.get("total"),
                "passed": summary.get("passed"),
                "failed": summary.get("failed"),
                "f2p_all_pass": summary.get("f2p_all_pass"),
                "p2p_all_pass": summary.get("p2p_all_pass"),
                "patch_applied": summary.get("patch_applied"),
                "evidence_dir": summary.get("evidence_dir"),
                "elapsed_sec": summary.get("elapsed"),
                "scored_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        })
        rep.pop("_note", None)
        pt.update({
            "task_id": "wfflab__wlogseg-218",
            "run_index": rep.get("run_index"),
            "source": "tests/test.ps1 的 aggregate-v1 result.json（二值：required F2P + required P2P 全过 = 1）",
            "results": {k: ("PASS" if v else "FAIL") for k, v in cases.items()},
            "f2p_all_pass": summary.get("f2p_all_pass"),
            "p2p_all_pass": summary.get("p2p_all_pass"),
        })
        pt.pop("_note", None)
    else:
        rep.update({
            "status": "INVALID",
            "score": None,
            "judge": {"engine": "tests/test.ps1",
                      "invalid_reason": summary.get("invalid_reason"),
                      "elapsed_sec": summary.get("elapsed")},
            "score_note": ("判分链路未产出可信 reward 产物，按契约不得记为 0 分；须修因后重判"),
        })
        rep.pop("_note", None)
    rep.pop("model_score_sum", None)
    write_json(rep_p, rep)
    write_json(pt_p, pt)
    write_json(run_dir / "judge" / (case + ".summary.json"), summary)


def main():
    ap = argparse.ArgumentParser(description="model_runs 补丁 → 本机判分 → 回填分数")
    ap.add_argument("--task", required=True, help="题包目录")
    ap.add_argument("--models", help="只判这些模型目录（逗号分隔），默认全部")
    ap.add_argument("--runs", help="只判这些轮次（逗号分隔，1-based），默认全部")
    ap.add_argument("--force", action="store_true", help="已回填的也重判")
    ap.add_argument("--out", help="判分沙箱根（默认 <task>/extras/model_runs/_judge）")
    a = ap.parse_args()

    task_dir = Path(a.task).resolve()
    runs_root = task_dir / "extras" / "model_runs"
    if not runs_root.is_dir():
        print("未找到 %s" % runs_root, file=sys.stderr)
        return 2
    judge_root = Path(a.out).resolve() if a.out else (runs_root / "_judge")
    judge_root.mkdir(parents=True, exist_ok=True)

    want_models = [s.strip() for s in a.models.split(",")] if a.models else None
    want_runs = [int(s) for s in a.runs.split(",")] if a.runs else None

    done = 0
    for mdir in sorted(p for p in runs_root.iterdir() if p.is_dir()):
        if mdir.name == "_judge":
            continue
        if want_models and mdir.name not in want_models:
            continue
        for rdir in sorted(mdir.glob("run-*")):
            try:
                n = int(rdir.name.split("-")[1])
            except Exception:
                continue
            if want_runs and n not in want_runs:
                continue
            rep = read_json(rdir / "report.json", {}) or {}
            case = "%s_r%d" % (mdir.name.replace("-", "_").replace(".", "_"), n)
            if not a.force and isinstance(rep.get("score"), (int, float)):
                print("  [skip] %s/%s: 已回填 score=%s" % (mdir.name, rdir.name, rep["score"]))
                continue
            print("  [judge] %s/%s ..." % (mdir.name, rdir.name))
            summ = judge_case(task_dir, rdir, case, judge_root)
            backfill(task_dir, rdir, case, summ)
            print("    status=%s score=%s validity=%s passed=%s/%s reason=%s (%.1fs)"
                  % (summ.get("status"), summ.get("score"), summ.get("run_validity"),
                     summ.get("passed"), summ.get("total"),
                     summ.get("invalid_reason"), summ.get("elapsed") or 0.0))
            done += 1
    print("判分完成：%d 个运行" % done)
    return 0


if __name__ == "__main__":
    sys.exit(main())
