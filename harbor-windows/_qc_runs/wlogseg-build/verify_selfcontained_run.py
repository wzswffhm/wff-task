# -*- coding: utf-8 -*-
"""verify_selfcontained_run.py —— 验证 218 题包**不依赖外部注入**即可判分。

新版甲方自检要求题包在容器内自洽（隐藏套件与参考解都在交付树里）。本脚本
故意**不设置** WLOGSEG_VERIFIER_ROOT / WLOGSEG_REFERENCE_ROOT，只靠包内路径：

  nop    : 交付初始态 → 期望 0
  golden : 包内 solution/reference/wlogseg（solve.ps1 候选 3）→ 期望 1

用法：python verify_selfcontained_run.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = ROOT / "harbor-windows" / "wfflab__wlogseg-218-v1.0.0-delivery"
OUT = ROOT / "harbor-windows" / "_qc_runs" / "wlogseg-build" / "selfcontained-218"
PY_DIR = r"C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python"
PYLIBS = str(ROOT / "harbor-windows" / "_qc_runs" / "wlogseg-build" / "pylibs")
PS_DIR = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                      "System32", "WindowsPowerShell", "v1.0")
PS_EXE = os.path.join(PS_DIR, "powershell.exe")


def env_clean() -> dict:
    """刻意不注入 verifier/reference 环境变量。"""
    env = dict(os.environ)
    for k in ("WLOGSEG_VERIFIER_ROOT", "WLOGSEG_REFERENCE_ROOT", "PYTHONUTF8",
              "PYTHONIOENCODING"):
        env.pop(k, None)
    env["PYTHONPATH"] = PYLIBS
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = os.pathsep.join([PY_DIR, PS_DIR, env.get("PATH", "")])
    return env


def run_case(name: str, golden: bool) -> dict:
    sandbox = OUT / name
    vdir = OUT / (name + "__verifier")
    if sandbox.exists():
        shutil.rmtree(sandbox, ignore_errors=True)
    if vdir.exists():
        shutil.rmtree(vdir, ignore_errors=True)
    shutil.copytree(PKG / "environment" / "workspace", sandbox)
    vdir.mkdir(parents=True)

    apply_exit = None
    if golden:
        p = subprocess.run([PS_EXE, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-NonInteractive", "-File", str(PKG / "solution" / "solve.ps1"),
                            "-TaskRoot", str(PKG), "-WorkspaceRoot", str(sandbox)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env_clean(), cwd=str(PKG), timeout=600)
        apply_exit = p.returncode
        (vdir / "solve.log").write_text((p.stdout or "") + (p.stderr or ""), encoding="utf-8")

    out_json = vdir / "result.json"
    p = subprocess.run([PS_EXE, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-NonInteractive", "-File", str(PKG / "tests" / "test.ps1"),
                        "-TaskRoot", str(PKG), "-WorkspaceRoot", str(sandbox),
                        "-OutputPath", str(out_json)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env_clean(), cwd=str(PKG), timeout=1800)
    (vdir / "stdout.log").write_text((p.stdout or "") + (p.stderr or ""), encoding="utf-8")

    doc = {}
    try:
        doc = json.loads(out_json.read_text(encoding="utf-8-sig"))
    except Exception:
        pass
    info = {"case": name, "expected": 1 if golden else 0, "solve_exit": apply_exit,
            "judge_exit": p.returncode, "score": doc.get("formal_score"),
            "validity": doc.get("run_validity"), "passed": doc.get("passed"),
            "total": doc.get("total"),
            "suite_line": next((ln for ln in (p.stdout or "").splitlines()
                                if ln.startswith("verifier: hidden suite")), "")}
    return info


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [run_case("nop", False), run_case("golden", True)]
    ok = all(r["score"] == r["expected"] and r["validity"] == "VALID" for r in rows)
    for r in rows:
        print("[%s] score=%s (期望 %s) validity=%s checks=%s/%s solve_exit=%s"
              % (r["case"], r["score"], r["expected"], r["validity"],
                 r["passed"], r["total"], r["solve_exit"]))
        print("    %s" % (r["suite_line"] or "(未打印隐藏套件解析行)"))
    (OUT / "selfcontained_summary.json").write_text(
        json.dumps({"rows": rows, "ok": ok}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("包内自洽（无外部注入）: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
