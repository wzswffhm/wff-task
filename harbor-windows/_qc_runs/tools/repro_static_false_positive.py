"""Minimal reproduction: feed the client QC's own static_check a task package that
follows their fixture shape, but whose scripts contain ordinary path literals
(the kind every real Windows task package must contain).

If static_pass is False, the check cannot be satisfied by any real package.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

QC = Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_ref\windows-harbor-qc\scripts")
sys.path.insert(0, str(QC))
from run_qc import static_check  # noqa: E402


def make_task(root: Path, *, script_body: str) -> None:
    """Same shape as the client's own tests/test_run_qc.py fixture."""
    (root / "environment").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "solution").mkdir()
    (root / "task.toml").write_text(
        'version = "1.0"\ndocker_image = "example/windows:20261001"\n\n[metadata]\ntask_id = "demo-001"\n',
        encoding="utf-8")
    (root / "source.json").write_text(json.dumps({
        "task_id": "demo-001", "source_type": "expert_constructed", "license": "internal",
        "lineage": "test", "authorization": "internal"}), encoding="utf-8")
    (root / "instruction.md").write_text("# Task\n", encoding="utf-8")
    for name in ("adapter.toml", "Dockerfile", "prepare.ps1", "validate_environment.ps1",
                 "run.ps1", "restore.ps1", "cleanup.ps1"):
        (root / "environment" / name).write_text("", encoding="utf-8")
    for name in ("test.ps1", "run_tests.ps1", "aggregate_results.ps1", "judge.toml"):
        (root / "tests" / name).write_text("", encoding="utf-8")
    (root / "tests" / "rubric.json").write_text(json.dumps({"task_id": "demo-001"}), encoding="utf-8")
    (root / "tests" / "required_testcases.json").write_text(json.dumps([
        {"id": "f2p-main", "group": "F2P"}, {"id": "p2p-regression", "group": "P2P"}
    ]), encoding="utf-8")
    (root / "solution" / "README.md").write_text("reference", encoding="utf-8")
    # Every real package has a solution entry point; give it an ordinary body.
    (root / "solution" / "solve.ps1").write_text(script_body, encoding="utf-8")


CASES = {
    "空脚本（甲方自测用的 fixture）": "",
    "注释里提到一个路径": "# see docs\\FORMAT.md for the contract\n",
    "脚本里引用容器内绝对路径": "$python = 'C:\\Python312\\python.exe'\n",
    "脚本里写产物文件名": "$log = Join-Path $results 'checks.json'\n",
    "脚本里用 %~dp0 拼同伴脚本": "robocopy \"%~dp0.\" C:\\tests /E\n",
    "脚本里引用工作区相对路径": "$module = Join-Path $root 'WReparse\\WReparse.psd1'\n",
}

for label, body in CASES.items():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "demo-001"
        make_task(root, script_body=body)
        report = static_check(root)
        status = "PASS" if report["static_pass"] else "FAIL"
        detail = report["errors"][0] if report["errors"] else ""
        print(f"[{status}] {label}")
        if detail:
            print(f"        {detail[:160]}")
