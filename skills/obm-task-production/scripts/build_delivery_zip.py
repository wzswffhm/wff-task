#!/usr/bin/env python3
"""Build an OBM delivery ZIP after the experiment and final check pass."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


FIXED_ZIP_TIME = (2000, 1, 1, 0, 0, 0)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manual_evidence_ok(result: dict, label: str) -> bool:
    """Validate explicit user-manual verifier evidence without Trae fields."""
    if result.get("execution_mode") != "user_manual":
        return False
    section = result.get(label, {})
    if not isinstance(section, dict):
        return False
    if label == "with_skill":
        path = Path(str(section.get("verifier", ""))).expanduser()
        try:
            verifier = read_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        return (
            verifier.get("status") == "completed"
            and int(verifier.get("container_exit_code", 1)) == 0
            and int(verifier.get("reward", 0)) == 1
            and int(section.get("reward", 0)) == 1
        )
    path = Path(str(section.get("source_result", ""))).expanduser()
    try:
        source = read_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return int(source.get("no_skill", {}).get("reward", 1)) == 0 and int(
        section.get("reward", 1)
    ) == 0


def turn_profile_ok(result: dict, label: str) -> bool:
    """Accept optional turn metadata without enforcing a range."""
    section = result.get(label, {})
    profile = section.get("turn_profile", {}) if isinstance(section, dict) else {}
    if not isinstance(profile, dict) or not profile:
        return True
    agent = section.get("agent", {})
    if not isinstance(agent, dict):
        agent = {}
    raw_turns = profile.get("turns", agent.get("turns"))
    if raw_turns is None:
        return True
    try:
        turns = int(raw_turns)
    except (TypeError, ValueError):
        return False
    return turns >= 0


def ensure_passed_experiment(path: Path) -> dict:
    result = read_json(path)
    automatic = (
        result.get("status") == "passed"
        and result.get("execution_mode") == "seed_api"
        and int(result.get("no_skill", {}).get("reward", 1)) == 0
        and int(result.get("with_skill", {}).get("reward", 0)) == 1
    )
    for label in ("no_skill", "with_skill"):
        agent = result.get(label, {}).get("agent", {})
        if not isinstance(agent, dict) or agent.get("completion_confirmed") is not True:
            if not (
                result.get("execution_mode") == "user_manual"
                and manual_evidence_ok(result, label)
            ):
                raise ValueError(f"{label} 缺少完成确认或有效手动 verifier 证据，禁止打包")
    if not automatic and result.get("execution_mode") != "user_manual":
        raise ValueError("实验未达到 no-skill reward=0、with-skill reward=1，禁止打包")
    return result


def ensure_passed_final_check(path: Path, task: Path, experiment_path: Path) -> dict:
    result = read_json(path)
    if result.get("ok") is not True:
        raise ValueError("FINAL_CHECK.json 的 ok 不是 true，禁止打包")
    recorded_task = Path(str(result.get("task_dir", ""))).expanduser().resolve()
    if recorded_task != task:
        raise ValueError("FINAL_CHECK.json 对应的题包与本次打包目录不一致")
    recorded_experiment = Path(
        str(result.get("experiment_result", ""))
    ).expanduser().resolve()
    if recorded_experiment != experiment_path:
        raise ValueError("FINAL_CHECK.json 对应的实验结果与本次打包输入不一致")
    recorded_experiment_hash = str(result.get("experiment_sha256", "")).strip()
    if not recorded_experiment_hash:
        raise ValueError("FINAL_CHECK.json 缺少实验结果散列，请重新运行最终质检")
    if sha256(experiment_path) != recorded_experiment_hash:
        raise ValueError("实验结果在最终质检后发生变化，请重新运行最终质检")
    screenshot = Path(str(result.get("screenshot", ""))).expanduser().resolve()
    if not screenshot.is_file() or screenshot.suffix.lower() != ".png":
        raise ValueError("FINAL_CHECK.png 不存在，禁止打包")
    recorded_screenshot_hash = str(result.get("screenshot_sha256", "")).strip()
    if not recorded_screenshot_hash:
        raise ValueError("FINAL_CHECK.json 缺少截图散列，请重新运行最终质检")
    if sha256(screenshot) != recorded_screenshot_hash:
        raise ValueError("FINAL_CHECK.png 的散列与 FINAL_CHECK.json 不一致")
    return result


def archive_task(task: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        root_name = task.name
        directory = zipfile.ZipInfo(f"{root_name}/", FIXED_ZIP_TIME)
        directory.external_attr = (stat.S_IFDIR | 0o755) << 16
        bundle.writestr(directory, b"")
        for path in sorted(task.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_symlink():
                raise ValueError(f"正式题包不能包含符号链接：{path.relative_to(task)}")
            relative = path.relative_to(task).as_posix()
            archive_name = f"{root_name}/{relative}"
            mode = path.stat().st_mode
            if path.is_dir():
                info = zipfile.ZipInfo(archive_name.rstrip("/") + "/", FIXED_ZIP_TIME)
                info.external_attr = (stat.S_IFDIR | (mode & 0o7777)) << 16
                bundle.writestr(info, b"")
                continue
            if not path.is_file():
                raise ValueError(f"正式题包包含不支持的文件类型：{path.relative_to(task)}")
            info = zipfile.ZipInfo(archive_name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | (mode & 0o7777)) << 16
            bundle.writestr(info, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--experiment-result", type=Path, required=True)
    parser.add_argument("--final-check", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--benchmark", default="deepSWE")
    args = parser.parse_args()

    task = args.task_dir.expanduser().resolve()
    experiment_path = args.experiment_result.expanduser().resolve()
    final_check_path = args.final_check.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not task.is_dir():
        raise ValueError(f"正式题包目录不存在：{task}")
    if not experiment_path.is_file():
        raise ValueError(f"实验结果不存在：{experiment_path}")
    if not final_check_path.is_file():
        raise ValueError(f"最终质检结果不存在：{final_check_path}")
    if output.suffix.lower() != ".zip":
        raise ValueError("交付文件必须使用 .zip 扩展名")
    if output.exists():
        raise ValueError(f"交付 ZIP 已存在，拒绝覆盖：{output}")
    if output == task or task in output.parents:
        raise ValueError("交付 ZIP 不能写入正式题包目录内部")

    ensure_passed_experiment(experiment_path)
    ensure_passed_final_check(final_check_path, task, experiment_path)

    output.parent.mkdir(parents=True, exist_ok=True)
    skill_dir = Path(__file__).resolve().parents[1]
    checker = skill_dir / "scripts/check_package.py"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{output.stem}-", suffix=".zip", dir=output.parent, delete=False
        ) as handle:
            temporary_path = Path(handle.name)
        archive_task(task, temporary_path)
        checked = subprocess.run(
            [
                sys.executable,
                str(checker),
                str(temporary_path),
                "--benchmark",
                args.benchmark,
            ],
            text=True,
            capture_output=True,
        )
        if checked.returncode != 0:
            details = (checked.stdout + checked.stderr).strip()
            raise ValueError("正式 ZIP 未通过 check_package.py：\n" + details)
        os.replace(temporary_path, output)
        output.chmod(0o644)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    print(
        json.dumps(
            {
                "ok": True,
                "task_dir": str(task),
                "experiment_result": str(experiment_path),
                "final_check": str(final_check_path),
                "zip": str(output),
                "zip_sha256": sha256(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        raise SystemExit(str(exc)) from exc
