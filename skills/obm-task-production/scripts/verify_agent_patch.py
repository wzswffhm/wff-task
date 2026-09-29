#!/usr/bin/env python3
"""Build and run a DeepSWE verifier against one Agent model.patch."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def prepare_app_context(app_src: Path, patch: Path, dest: Path) -> Path:
    """Stage a copy of sources/app with the Agent model.patch applied.

    The verifier must grade the *patched* source, not the pristine baseline
    (see references/deepswe.md). The Agent may work in a tree whose layout
    differs from sources/app (e.g. app is a flattened package while the patch
    targets ``src/...``), and a real patch usually also touches files that are
    not part of the graded app (tests/, docs/, CI config). We therefore keep
    only the hunks whose target path exists in the app copy at some strip
    level, rewrite their headers to that path, and apply with ``patch -p1``.
    An empty / no-op patch yields the baseline.
    """
    shutil.copytree(app_src, dest)
    raw = patch.read_text(encoding="utf-8", errors="replace")
    if not any(
        line.startswith(("--- ", "+++ ", "diff --git")) for line in raw.splitlines()
    ):
        return dest  # empty patch == no change to baseline

    def match_target(section: str) -> str | None:
        plus = re.search(r"(?m)^\+\+\+ b/(.+?)\s*$", section)
        minus = re.search(r"(?m)^--- a/(.+?)\s*$", section)
        source = plus.group(1) if plus else (minus.group(1) if minus else None)
        if not source:
            return None
        is_new = "--- /dev/null" in section
        parts = source.split("/")
        for level in range(0, 5):
            candidate = "/".join(parts[level:])
            if not candidate:
                continue
            target = dest / candidate
            if target.exists() or (is_new and target.parent.is_dir()):
                return candidate
        return None

    kept: list[str] = []
    for section in re.split(r"(?m)^(?=diff --git )", raw):
        if not section.strip():
            continue
        candidate = match_target(section)
        if candidate is None:
            continue  # 不属于本题包（tests/、docs/、CI 配置……）
        section = re.sub(
            r"(?m)^diff --git a/.+ b/.+$",
            f"diff --git a/{candidate} b/{candidate}",
            section,
            count=1,
        )
        section = re.sub(r"(?m)^--- a/.+$", f"--- a/{candidate}", section, count=1)
        section = re.sub(r"(?m)^\+\+\+ b/.+$", f"+++ b/{candidate}", section, count=1)
        kept.append(section)
    if not kept:
        # The Agent made no change to the graded source (e.g. it failed, or only
        # touched tests/docs). Grading the pristine baseline is correct here and
        # must yield reward 0, not an infrastructure error.
        return dest

    staged_patch = dest.parent / (dest.name + ".patch")
    staged_patch.write_text("".join(kept), encoding="utf-8")
    check = subprocess.run(
        ["patch", "--dry-run", "-p1", "--no-backup-if-mismatch", "-i", str(staged_patch)],
        cwd=dest, text=True, capture_output=True,
    )
    if check.returncode != 0:
        raise SystemExit(
            "无法将 model.patch 的源码改动应用到 sources/app：\n"
            + (check.stdout + check.stderr).strip()
        )
    subprocess.run(
        ["patch", "-p1", "--no-backup-if-mismatch", "-i", str(staged_patch)],
        cwd=dest, text=True, capture_output=True, check=True,
    )
    return dest


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

    # Grade the patched source: stage sources/app with model.patch applied.
    app_context = output / "app-context"
    prepare_app_context(app, patch, app_context)

    fingerprint = hashlib.sha256(
        (tree_hash(app_context) + tree_hash(verifier)).encode()
    ).hexdigest()[:16]
    app_image = f"obm-trae-app:{fingerprint}"
    verifier_image = f"obm-trae-verifier:{fingerprint}"

    app_rc = run_logged(
        [
            args.docker,
            "build",
            "--network=none",
            "-t",
            app_image,
            str(app_context),
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
