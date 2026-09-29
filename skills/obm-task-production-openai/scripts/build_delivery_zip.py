#!/usr/bin/env python3
"""Build the formal OBM ZIP after Seed evidence and final check pass."""

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
from typing import Optional


FIXED_ZIP_TIME = (2000, 1, 1, 0, 0, 0)

# Entrypoints that must carry the executable bit inside the verifier container.
EXECUTABLE_ENTRYPOINTS = {
    "sources/verifier/test.sh",
    "sources/verifier/grader.py",
}

# digest-pinned python image used for authoritative package checks on Windows
# hosts (Windows filesystems cannot represent POSIX executable bits).
CHECK_IMAGE = "python@sha256:4d1caded1f729ae443eb803f26ffde7b61e696aeaef62f099abb6dd6b14257c7"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_passed_experiment(path: Path) -> dict:
    result = read_json(path)
    if not (
        result.get("status") == "passed"
        and result.get("execution_mode") == "seed_api"
        and int(result.get("no_skill", {}).get("reward", 1)) == 0
        and int(result.get("with_skill", {}).get("reward", 0)) == 1
    ):
        raise ValueError("实验未达到 no-skill reward=0、with-skill reward=1，禁止打包")
    for label in ("no_skill", "with_skill"):
        agent = result.get(label, {}).get("agent", {})
        if not isinstance(agent, dict) or agent.get("completion_confirmed") is not True:
            raise ValueError(f"{label} 缺少 Agent 完成确认，禁止打包")
    return result


def ensure_turn_stats(path: Path) -> dict:
    stats = read_json(path)
    if stats.get("strict_acceptance", {}).get("passed") is not True:
        raise ValueError("TURN_STATS.json 未通过严格 reward 对照，禁止打包")
    turns = stats.get("turns", {})
    if not isinstance(turns.get("no_skill"), int) or not isinstance(
        turns.get("with_skill"), int
    ):
        raise ValueError("TURN_STATS.json 缺少有效轮次统计，禁止打包")
    return stats


def ensure_passed_final_check(
    path: Path,
    task: Path,
    experiment_path: Path,
    turn_stats_path: Path,
) -> dict:
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
    recorded_turn_stats = Path(str(result.get("turn_stats", ""))).expanduser().resolve()
    if recorded_turn_stats != turn_stats_path:
        raise ValueError("FINAL_CHECK.json 对应的轮次统计与本次打包输入不一致")
    if sha256(experiment_path) != str(result.get("experiment_sha256", "")):
        raise ValueError("实验结果在最终质检后发生变化，请重新运行最终质检")
    if sha256(turn_stats_path) != str(result.get("turn_stats_sha256", "")):
        raise ValueError("轮次统计在最终质检后发生变化，请重新运行最终质检")
    screenshot = Path(str(result.get("screenshot", ""))).expanduser().resolve()
    if not screenshot.is_file() or screenshot.suffix.lower() != ".png":
        raise ValueError("FINAL_CHECK.png 不存在，禁止打包")
    if sha256(screenshot) != str(result.get("screenshot_sha256", "")):
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
            if sys.platform == "win32" and not path.is_dir():
                # Windows CPython 无法读取/设置 POSIX 可执行位（st_mode 恒 0o666）。
                # 按包结构规范化文件权限：verifier 入口固定 0o755，其余 0o644，
                # 保证 ZIP 在 Linux 验收环境解压后可直接执行。
                mode = 0o755 if relative in EXECUTABLE_ENTRYPOINTS else 0o644
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


def run_package_checker(
    checker: Path, package: Path, benchmark: str
) -> subprocess.CompletedProcess:
    if sys.platform != "win32":
        return subprocess.run(
            [
                sys.executable,
                str(checker),
                str(package),
                "--benchmark",
                benchmark,
            ],
            text=True,
            capture_output=True,
        )
    # Windows 无法从 st_mode 还原可执行位（safe_extract 重放 mode 后宿主机
    # 依旧读到 0o666），ZIP 自检放进 Linux 容器执行，与官方验收环境一致。
    skill_root = checker.parent.parent
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{package.parent.as_posix()}:/pkg",
            "-v",
            f"{skill_root.as_posix()}:/skill:ro",
            CHECK_IMAGE,
            "python3",
            "/skill/scripts/check_package.py",
            f"/pkg/{package.name}",
            "--benchmark",
            benchmark,
        ],
        text=True,
        capture_output=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--experiment-result", type=Path, required=True)
    parser.add_argument("--turn-stats", type=Path, required=True)
    parser.add_argument("--final-check", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--benchmark", default="deepSWE")
    args = parser.parse_args()

    task = args.task_dir.expanduser().resolve()
    experiment_path = args.experiment_result.expanduser().resolve()
    turn_stats_path = args.turn_stats.expanduser().resolve()
    final_check_path = args.final_check.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not task.is_dir():
        raise ValueError(f"正式题包目录不存在：{task}")
    for required in (experiment_path, turn_stats_path, final_check_path):
        if not required.is_file():
            raise ValueError(f"打包输入不存在：{required}")
    if output.suffix.lower() != ".zip":
        raise ValueError("交付文件必须使用 .zip 扩展名")
    if output.exists():
        raise ValueError(f"交付 ZIP 已存在，拒绝覆盖：{output}")
    if output == task or task in output.parents:
        raise ValueError("交付 ZIP 不能写入正式题包目录内部")

    ensure_passed_experiment(experiment_path)
    ensure_turn_stats(turn_stats_path)
    ensure_passed_final_check(
        final_check_path, task, experiment_path, turn_stats_path
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    skill_dir = Path(__file__).resolve().parents[1]
    checker = skill_dir / "scripts/check_package.py"
    temporary_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{output.stem}-",
            suffix=".zip",
            dir=output.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
        archive_task(task, temporary_path)
        checked = run_package_checker(checker, temporary_path, args.benchmark)
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
                "turn_stats": str(turn_stats_path),
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
