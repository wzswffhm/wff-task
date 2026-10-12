#!/usr/bin/env python3
"""Build and run a DeepSWE verifier against one Agent model.patch."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run_logged(command: list[str], log: Path, cwd: Path | None = None) -> int:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    log.write_text(
        "$ " + " ".join(command) + "\n\n" + result.stdout + result.stderr,
        encoding="utf-8",
    )
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--docker", default="docker")
    args = parser.parse_args()

    task = args.task_dir.expanduser().resolve()
    patch = args.patch.expanduser().resolve()
    output = args.output_dir.expanduser().resolve()
    app = task / "sources/app"
    verifier = task / "sources/verifier"
    if not app.is_dir() or not verifier.is_dir():
        raise SystemExit("题包缺少 sources/app 或 sources/verifier")
    if not patch.is_file():
        raise SystemExit(f"找不到 model.patch：{patch}")
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"验证输出目录非空，拒绝覆盖：{output}")
    output.mkdir(parents=True, exist_ok=True)
    artifacts = output / "artifacts"
    logs = output / "logs"
    artifacts.mkdir()
    logs.mkdir()
    (artifacts / "model.patch").write_bytes(patch.read_bytes())

    fingerprint = hashlib.sha256(
        (tree_hash(app) + tree_hash(verifier)).encode()
    ).hexdigest()[:16]
    app_image = f"obm-seed-app:{fingerprint}"
    verifier_image = f"obm-seed-verifier:{fingerprint}"

    app_rc = run_logged(
        [
            args.docker,
            "build",
            "--network=none",
            "-t",
            app_image,
            str(app),
        ],
        output / "APP_BUILD.log",
    )
    if app_rc != 0:
        result = {"status": "infrastructure_error", "stage": "app_build", "reward": None}
        (output / "VERIFICATION.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    verifier_rc = run_logged(
        [
            args.docker,
            "build",
            "--network=none",
            "--build-arg",
            f"APP_IMAGE={app_image}",
            "-t",
            verifier_image,
            str(verifier),
        ],
        output / "VERIFIER_BUILD.log",
    )
    if verifier_rc != 0:
        result = {
            "status": "infrastructure_error",
            "stage": "verifier_build",
            "reward": None,
        }
        (output / "VERIFICATION.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    run_rc = run_logged(
        [
            args.docker,
            "run",
            "--rm",
            "--network=none",
            "-v",
            f"{artifacts}:/logs/artifacts",
            "-v",
            f"{logs}:/logs/verifier",
            verifier_image,
        ],
        output / "VERIFIER_RUN.log",
    )
    reward_path = logs / "reward.json"
    if reward_path.is_file():
        reward = json.loads(reward_path.read_text(encoding="utf-8"))
        result = {
            "status": "completed",
            "stage": "grade",
            "container_exit_code": run_rc,
            **reward,
        }
    else:
        sentinel = logs / "reward.txt"
        result = {
            "status": "infrastructure_error",
            "stage": "verifier_run",
            "container_exit_code": run_rc,
            "reward": None,
            "reward_sentinel": sentinel.read_text().strip() if sentinel.is_file() else None,
        }
    (output / "VERIFICATION.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
