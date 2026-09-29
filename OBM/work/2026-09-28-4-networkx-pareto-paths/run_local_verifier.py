#!/usr/bin/env python
"""本地 NOP / ORACLE 验证（不经 Docker）：构建干净 app 树 → 可选应用补丁 → 跑 verifier/grader.py。

用法：
  python run_local_verifier.py --task-dir <题包目录> [--patch <model.patch>]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_SCRIPTS = Path(
    r"C:/Users/Administrator/Desktop/OBM/skills/obm-task-production/scripts"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-dir", required=True)
    ap.add_argument("--patch")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    task = Path(args.task_dir).resolve()
    app_src = task / "sources/app"
    verifier_src = task / "sources/verifier"

    tmp = Path(tempfile.mkdtemp(prefix="obm-local-"))
    if args.patch:
        sys.path.insert(0, str(SKILL_SCRIPTS))
        from verify_agent_patch import prepare_app_context  # noqa: PLC0415

        app = tmp / "app-context"
        prepare_app_context(app_src, Path(args.patch).resolve(), app)
    else:
        app = tmp / "app"
        shutil.copytree(app_src, app)

    verifier = tmp / "verifier"
    shutil.copytree(verifier_src, verifier)

    env = dict(os.environ)
    env["APP_DIR"] = str(app)
    env["TESTS_DIR"] = str(verifier / "tests")
    proc = subprocess.run(
        [args.python, str(verifier / "grader.py")],
        cwd=str(verifier),
        env=env,
        text=True,
        capture_output=True,
    )
    print(proc.stdout.strip()[-3000:])
    if proc.returncode != 0:
        print("STDERR:", proc.stderr.strip()[-1500:])

    report_path = verifier / "report.json"
    if report_path.is_file():
        rep = json.loads(report_path.read_text(encoding="utf-8"))
        tag = args.label or ("ORACLE" if args.patch else "NOP")
        print(f"\n===== {tag} =====")
        print("REWARD =", rep["reward"])
        for suite in ("f2p", "p2p"):
            s = rep[suite]
            print(
                f"  {suite}: expected={s['expected']} passed={s['passed']} "
                f"missing={len(s['missing'])} not_passed={len(s['not_passed'])}"
            )
            for i in (s["missing"] + s["not_passed"])[:5]:
                print("    -", i)
    print(f"[tmp] {tmp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
