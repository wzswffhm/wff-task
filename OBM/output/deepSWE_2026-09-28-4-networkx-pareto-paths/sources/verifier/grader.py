#!/usr/bin/env python
"""Behavioral verifier for the networkx ``pareto_paths`` task.

Runs two suites against the (possibly patched) app tree and emits a binary
reward: 1 only when every listed F2P and every listed P2P node reports
``passed``. Missing / failed / error / skipped nodes all count as failures.

Layout assumption:
  <APP_DIR>/networkx          -- the (possibly patched) upstream package
  <TESTS_DIR>                 -- the verifier's own F2P suite (a ``tests`` package)
  <HERE>/pristine/<path>      -- pristine copies of the P2P test files, restored
                                 into APP_DIR before grading so that tampering
                                 with in-tree tests cannot fake a regression pass
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_pytest(args, cwd, outcomes_path, pythonpath):
    env = os.environ.copy()
    parts = [str(p) for p in pythonpath]
    existing = env.get("PYTHONPATH", "")
    if existing:
        parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["OBM_OUTCOMES"] = str(outcomes_path)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *args,
        "-q",
        "-p",
        "no:cacheprovider",
        "-p",
        "_obm_plugin",
        "--no-header",
        "-o",
        "addopts=",
    ]
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True)
    if outcomes_path.is_file():
        try:
            return json.loads(outcomes_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    print(proc.stdout[-2000:], file=sys.stderr)
    print(proc.stderr[-2000:], file=sys.stderr)
    return {}


def restore_pristine(app_dir: Path, pristine_dir: Path) -> int:
    restored = 0
    if not pristine_dir.is_dir():
        return restored
    for src in pristine_dir.rglob("*"):
        if not src.is_file():
            continue
        dst = app_dir / src.relative_to(pristine_dir)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        restored += 1
    return restored


def inject_f2p(app_dir: Path, verifier_dir: Path) -> Path:
    """把 F2P 套件注入 app 树（优先用 test.patch，失败则复制 tests/）。

    注入到 <APP>/tests 后，以 app 为 cwd、tests 为参数运行 pytest，nodeid 恒为
    tests/test_pareto_paths.py::test_x，与 config.json 白名单一致。
    """
    target = app_dir / "tests"
    if (target / "test_pareto_paths.py").is_file():
        return target
    patch_path = verifier_dir / "test.patch"
    if patch_path.is_file():
        if (app_dir / ".git").is_dir():
            proc = subprocess.run(
                ["git", "-C", str(app_dir), "apply", "--whitespace=nowarn", str(patch_path)],
                capture_output=True, text=True,
            )
        else:
            proc = subprocess.run(
                ["patch", "-p1", "--forward", "--no-backup-if-mismatch", "-i", str(patch_path)],
                cwd=str(app_dir), capture_output=True, text=True,
            )
        if proc.returncode == 0 and (target / "test_pareto_paths.py").is_file():
            return target
    shutil.copytree(verifier_dir / "tests", target, dirs_exist_ok=True)
    return target


def main():
    here = Path(__file__).resolve().parent
    app_dir = Path(os.environ.get("APP_DIR", "/app"))

    config_path = here / "config.json"
    if not config_path.exists():
        print("ERROR: config.json not found", file=sys.stderr)
        return 2
    config = json.loads(config_path.read_text(encoding="utf-8"))
    f2p_ids = config.get("f2p_node_ids", [])
    p2p_ids = config.get("p2p_node_ids", [])

    restored = restore_pristine(app_dir, here / "pristine")
    f2p_dir = inject_f2p(app_dir, here)

    outcomes = {}
    # 以 app 为 cwd、注入目录名为参数，保证 nodeid 形如 tests/test_x.py::test_y。
    outcomes.update(
        run_pytest(
            [f2p_dir.name],
            app_dir,
            here / "outcomes-f2p.json",
            [app_dir, here],
        )
    )
    if p2p_ids:
        outcomes.update(
            run_pytest(list(p2p_ids), app_dir, here / "outcomes-p2p.json", [app_dir, here])
        )

    def audit(ids):
        missing = [i for i in ids if i not in outcomes]
        not_passed = [i for i in ids if outcomes.get(i) != "passed"]
        passed = sum(1 for i in ids if outcomes.get(i) == "passed")
        return missing, not_passed, passed

    f2p_missing, f2p_failed, f2p_passed = audit(f2p_ids)
    p2p_missing, p2p_failed, p2p_passed = audit(p2p_ids)

    reward = 1 if not (f2p_missing or f2p_failed or p2p_missing or p2p_failed) else 0

    report = {
        "reward": reward,
        "restored_pristine_files": restored,
        "f2p": {
            "expected": len(f2p_ids),
            "missing": f2p_missing,
            "not_passed": f2p_failed,
            "passed": f2p_passed,
        },
        "p2p": {
            "expected": len(p2p_ids),
            "missing": p2p_missing,
            "not_passed": p2p_failed,
            "passed": p2p_passed,
        },
    }
    (here / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"REWARD={reward}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
