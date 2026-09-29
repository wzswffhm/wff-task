#!/usr/bin/env python
"""Behavioral verifier for the pycasbin ``enforce_traced`` / ``would_change`` task.

Runs the F2P (feature) and P2P (regression) pytest suites and emits a binary
reward: 1 only when every listed F2P and every listed P2P test reports
``passed``. Any missing / failed / error / skipped node counts as a failure.

Layout assumption:
  <APP_DIR>/casbin   -- the (possibly patched) upstream package
  <TESTS_DIR>        -- the verifier test suite (a ``tests`` package)
"""
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MODEL_PATCH = Path(os.environ.get("MODEL_PATCH", "/logs/artifacts/model.patch"))


def prepare_app(app_dir: Path) -> tuple[bool, str]:
    """Apply the Agent model.patch to APP_DIR when the orchestrator provides one.

    Mirrors the official deepSWE collect flow: the verifier consumes the
    ``model.patch`` that the Agent run wrote to ``/logs/artifacts``. Returns
    ``(ok, message)``; a patch that cannot be applied is a structured failure
    and grades as reward 0.
    """
    global MODEL_PATCH
    if not MODEL_PATCH.is_file() or MODEL_PATCH.stat().st_size == 0:
        return True, "no model.patch provided; grading the pristine app"
    # The verifier tree is LF-only. An Agent patch produced on a platform with
    # CRLF text-mode translation would fail to apply line-for-line; normalize
    # the patch bytes (content is unchanged) before applying.
    patch_bytes = MODEL_PATCH.read_bytes()
    if b"\r\n" in patch_bytes:
        normalized = app_dir / ".obm-model-patch.normalized"
        normalized.write_bytes(patch_bytes.replace(b"\r\n", b"\n"))
        MODEL_PATCH = normalized
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={app_dir}",
            "apply",
            "--whitespace=nowarn",
            str(MODEL_PATCH),
        ],
        cwd=str(app_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return False, detail[:2000] or f"git apply exited {result.returncode}"
    return True, "model.patch applied to APP_DIR"


def run_pytest(tests_dir: Path, app_dir: Path, report_path: Path) -> int:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    parts = [str(app_dir), str(tests_dir.parent)]
    if existing:
        parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(parts)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(tests_dir),
        "--junit-xml",
        str(report_path),
        "-q",
        "-p",
        "no:cacheprovider",
        "--no-header",
        "-o",
        "addopts=",
    ]
    result = subprocess.run(
        cmd,
        cwd=str(tests_dir.parent),
        env=env,
        capture_output=True,
        text=True,
    )
    return result.returncode


def parse_outcomes(report_path: Path) -> dict[str, str]:
    outcomes: dict[str, str] = {}
    if not report_path.exists():
        return outcomes
    try:
        root = ET.parse(report_path).getroot()
    except ET.ParseError:
        return outcomes
    for tc in root.iter("testcase"):
        classname = tc.get("classname", "")
        name = tc.get("name", "")
        parts = classname.split(".")
        if len(parts) < 2:
            continue
        module_file = f"{parts[0]}/{parts[1]}.py"
        class_part = parts[2:]
        node = "::".join([module_file, *class_part, name])
        if tc.find("failure") is not None or tc.find("error") is not None:
            outcome = "failed"
        elif tc.find("skipped") is not None or tc.find("xfailed") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        outcomes[node] = outcome
    return outcomes


def main() -> int:
    here = Path(__file__).resolve().parent
    work = here.parent
    app_dir = Path(os.environ.get("APP_DIR", str(work / "app")))
    tests_dir = Path(os.environ.get("TESTS_DIR", str(work / "tests")))
    config_path = here / "config.json"
    report_path = Path(os.environ.get("REPORT_PATH", str(here / "junit.xml")))

    if not config_path.exists():
        print("ERROR: config.json not found", file=sys.stderr)
        return 2

    config = json.loads(config_path.read_text(encoding="utf-8"))
    f2p = config.get("f2p_node_ids", [])
    p2p = config.get("p2p_node_ids", [])

    apply_ok, apply_message = prepare_app(app_dir)
    print(f"PATCH_PREPARE={'ok' if apply_ok else 'failed'}: {apply_message}")
    if not apply_ok:
        print("ERROR: Agent model.patch could not be applied", file=sys.stderr)
        report = {
            "reward": 0,
            "status": "patch_apply_failed",
            "detail": apply_message,
            "f2p": {"expected": len(f2p), "missing": list(f2p), "not_passed": [], "passed": 0},
            "p2p": {"expected": len(p2p), "missing": [], "not_passed": [], "passed": 0},
        }
        (here / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({k: v for k, v in report.items() if k != "outcomes"}, indent=2))
        print("REWARD=0")
        return 0

    run_pytest(tests_dir, app_dir, report_path)
    outcomes = parse_outcomes(report_path)

    def audit(ids):
        present = {i: outcomes.get(i, "missing") for i in ids}
        missing = [i for i in ids if i not in outcomes]
        not_passed = [i for i in ids if outcomes.get(i) != "passed"]
        passed = sum(1 for i in ids if outcomes.get(i) == "passed")
        return missing, not_passed, passed

    f2p_missing, f2p_failed, f2p_passed = audit(f2p)
    p2p_missing, p2p_failed, p2p_passed = audit(p2p)

    reward = 1 if not (f2p_missing or f2p_failed or p2p_missing or p2p_failed) else 0

    report = {
        "reward": reward,
        "f2p": {
            "expected": len(f2p),
            "missing": f2p_missing,
            "not_passed": f2p_failed,
            "passed": f2p_passed,
        },
        "p2p": {
            "expected": len(p2p),
            "missing": p2p_missing,
            "not_passed": p2p_failed,
            "passed": p2p_passed,
        },
        "outcomes": outcomes,
    }

    (here / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "outcomes"}, indent=2
        )
    )
    print(f"REWARD={reward}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
