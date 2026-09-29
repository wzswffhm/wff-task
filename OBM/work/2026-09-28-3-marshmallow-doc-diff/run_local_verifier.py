#!/usr/bin/env python
"""Local equivalent of the Docker verifier run.

Builds a clean 'nop' tree (unmodified upstream) and an 'oracle' tree (upstream +
reference implementation) and runs the grader against each, capturing the binary
reward. This is the same grader the benchmark harness uses; only the environment
(network, filesystem) differs from the official Docker run.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = Path(r"C:\Users\Administrator\Desktop\OBM\output\deepSWE_2026-09-28-3-marshmallow-doc-diff")
APP_SRC = PKG / "sources" / "app"
VERIFIER = PKG / "sources" / "verifier"
REF_SCHEMA = ROOT / "baseline" / "src" / "marshmallow" / "schema.py"  # reference impl
RUNS = ROOT / "runs"

VP = r"C:\Users\Administrator\.workbuddy\binaries\python\envs\obm\Scripts\python.exe"


def build_tree(name: str, with_ref: bool) -> Path:
    tree = RUNS / name
    app = tree / "app"
    tests = tree / "tests"
    # dirs_exist_ok avoids rmtree (blocked by sandbox safe-delete) and refreshes in place
    shutil.copytree(APP_SRC, app, dirs_exist_ok=True)
    shutil.copytree(VERIFIER / "tests", tests, dirs_exist_ok=True)
    shutil.copy2(VERIFIER / "grader.py", tree / "grader.py")
    shutil.copy2(VERIFIER / "config.json", tree / "config.json")
    if with_ref:
        shutil.copy2(REF_SCHEMA, app / "marshmallow" / "schema.py")
    return tree


def run(tree: Path, label: str) -> int:
    env = os.environ.copy()
    env["APP_DIR"] = str(tree / "app")
    env["TESTS_DIR"] = str(tree / "tests")
    env["REPORT_PATH"] = str(tree / "report.jsonl")
    result = subprocess.run(
        [VP, str(tree / "grader.py")],
        cwd=str(tree),
        env=env,
        capture_output=True,
        text=True,
    )
    print(f"\n===== {label} (tree={tree.name}) =====")
    print(result.stdout)
    if result.stderr.strip():
        print("STDERR:", result.stderr[-1500:])
    # grader prints REWARD=<0|1>; parse it
    reward = 0
    for line in result.stdout.splitlines():
        if line.startswith("REWARD="):
            try:
                reward = int(line.split("=", 1)[1].strip())
            except ValueError:
                reward = 0
    return reward


def main() -> int:
    rewards = {}
    nop = build_tree("nop", with_ref=False)
    rewards["nop"] = run(nop, "NOP (clean upstream baseline)")
    oracle = build_tree("oracle", with_ref=True)
    rewards["oracle"] = run(oracle, "ORACLE (reference implementation)")
    print("\n===== SUMMARY =====")
    print("NOP reward   :", rewards["nop"])
    print("ORACLE reward:", rewards["oracle"])
    ok = (rewards["nop"] == 0) and (rewards["oracle"] == 1)
    print("EXPECTED (NOP=0, ORACLE=1):", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
