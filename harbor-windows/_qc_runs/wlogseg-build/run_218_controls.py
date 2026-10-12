# -*- coding: utf-8 -*-
"""run_218_controls.py —— 218 题包的 Golden / no-change 六轮对照（真实 Windows Runtime）。

与 judge_runs.py 同一判分链路（tests/test.ps1 + WLOGSEG_VERIFIER_ROOT 注入隐藏套件），
差别只在于载荷：

  * golden-N  ：复制 environment/workspace 后先跑 solution/solve.ps1 注入参考解，再判分 → 期望 1
  * nop-N     ：复制 environment/workspace 原样判分（no-change）          → 期望 0

用法：
    python run_218_controls.py [--rounds 3]
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

PKG_NAME = "wfflab__wlogseg-218-v1.0.0-delivery"
ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = ROOT / "harbor-windows" / PKG_NAME
OUT = ROOT / "harbor-windows" / "_qc_runs" / "wlogseg-build" / "controls-218"
PY = r"C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
PYLIBS = r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\wlogseg-build\pylibs"
PS_DIR = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                      "System32", "WindowsPowerShell", "v1.0")
PS_EXE = os.path.join(PS_DIR, "powershell.exe")


def sh(args, cwd=None, timeout=1800, env=None):
    p = subprocess.run(args, cwd=str(cwd) if cwd else None, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, env=env)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def read_json(p: Path, default=None):
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


def judge_env():
    env = dict(os.environ)
    env["WLOGSEG_VERIFIER_ROOT"] = str(PKG / "verifier")
    env["PYTHONPATH"] = PYLIBS + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = os.pathsep.join([os.path.dirname(PY), PS_DIR, env.get("PATH", "")])
    for k in ("PYTHONUTF8", "PYTHONIOENCODING"):
        env.pop(k, None)
    return env


def run_case(case: str, golden: bool) -> dict:
    sandbox = OUT / case
    vdir = OUT / (case + "__verifier")
    summary = {"case": case, "role": "oracle" if golden else "nop",
               "expected_score": 1 if golden else 0, "status": "INVALID",
               "score": None, "run_validity": None, "total": None, "passed": None,
               "failed": None, "oracle_apply_exit": None, "elapsed": None}

    workspace = PKG / "environment" / "workspace"
    if not workspace.is_dir():
        summary["invalid_reason"] = "workspace_missing"
        return summary

    clean_dir(sandbox)
    clean_dir(vdir)
    shutil.copytree(workspace, sandbox)

    if golden:
        rc, o, e = sh([PS_EXE, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
                       "-NonInteractive", "-File", str(PKG / "solution" / "solve.ps1"),
                       "-TaskRoot", str(PKG), "-WorkspaceRoot", str(sandbox),
                       "-ReferenceRoot", str(PKG / "verifier" / "oracle" / "reference" / "wlogseg")],
                      cwd=PKG, timeout=600, env=judge_env())
        summary["oracle_apply_exit"] = rc
        (vdir / (case + ".solve.log")).parent.mkdir(parents=True, exist_ok=True)
        (vdir / (case + ".solve.log")).write_text((o or "") + (e or ""), encoding="utf-8")
        if rc != 0:
            summary["invalid_reason"] = "oracle_apply_failed"
            return summary

    env = judge_env()
    vdir.mkdir(parents=True, exist_ok=True)
    out_json = vdir / "result.json"
    t0 = time.time()
    rc, o, e = sh([PS_EXE, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
                   "-NonInteractive", "-File", str(PKG / "tests" / "test.ps1"),
                   "-TaskRoot", str(PKG), "-WorkspaceRoot", str(sandbox),
                   "-OutputPath", str(out_json)], cwd=PKG, timeout=1800, env=env)
    summary["elapsed"] = round(time.time() - t0, 2)
    (vdir / (case + ".stdout.log")).write_text((o or "") + (e or ""), encoding="utf-8")
    summary["exit_code"] = rc

    doc = read_json(out_json)
    if not isinstance(doc, dict):
        summary["invalid_reason"] = "judge_result_missing"
        return summary
    summary.update({
        "status": "VALID",
        "score": doc.get("formal_score"),
        "run_validity": doc.get("run_validity"),
        "total": doc.get("total"),
        "passed": doc.get("passed"),
        "failed": doc.get("failed"),
        "invalid": doc.get("invalid"),
    })
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for role, golden in (("golden", True), ("nop", False)):
        for n in range(1, a.rounds + 1):
            case = "%s-%d" % (role, n)
            print("[%s] %s ..." % (time.strftime("%H:%M:%S"), case), flush=True)
            s = run_case(case, golden)
            write_json(OUT / (case + ".summary.json"), s)
            print("    status=%s score=%s validity=%s passed=%s/%s expected=%s (%.1fs)"
                  % (s.get("status"), s.get("score"), s.get("run_validity"),
                     s.get("passed"), s.get("total"), s.get("expected_score"),
                     s.get("elapsed") or 0.0), flush=True)
            rows.append(s)

    ok = all(r.get("status") == "VALID" and r.get("score") == r.get("expected_score")
             for r in rows)
    write_json(OUT / "controls_summary.json", {
        "task_id": "wfflab__wlogseg-218",
        "package": str(PKG),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rounds": rows,
        "all_as_expected": ok,
    })
    print("六轮对照全部符合预期: %s" % ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
