#!/usr/bin/env python3
"""Resolve and launch one exact Trae workspace for an OBM experiment stage."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def repo_path(baseline: dict, mode_dir: Path, mode: str) -> Path:
    names = baseline.get("repo_dir_names")
    name = names.get(mode) if isinstance(names, dict) else None
    if not name:
        name = baseline.get("repo_dir_name")
    if not isinstance(name, str) or not name:
        raise ValueError("BASELINE.json 缺少当前模式的仓库目录名")
    return (mode_dir / name).resolve()


def load_stage(run_root: Path, mode: str) -> tuple[dict, Path, Path, Path]:
    baseline_path = run_root / "BASELINE.json"
    if not baseline_path.is_file():
        raise ValueError(f"缺少 BASELINE.json：{baseline_path}")
    baseline = read_json(baseline_path)
    mode_name = baseline.get("mode_dirs", {}).get(mode)
    if not isinstance(mode_name, str) or not mode_name:
        raise ValueError(f"BASELINE.json 缺少 {mode} 目录映射")
    mode_dir = (run_root / mode_name).resolve()
    repo = repo_path(baseline, mode_dir, mode)
    prompt = mode_dir / "PROMPT.md"
    if not repo.is_dir() or not prompt.is_file():
        raise ValueError(f"Trae 工作区材料不完整：{mode_dir}")
    expected_prompt = baseline.get(
        "no_skill_prompt_sha256" if mode == "no-skill" else "with_skill_prompt_sha256"
    )
    actual_prompt = sha256(prompt)
    if expected_prompt != actual_prompt:
        raise ValueError("PROMPT.md 散列与 BASELINE.json 不一致")
    if (mode_dir / "TRAE_RUN.json").exists():
        raise ValueError("该阶段已经提交并登记，不能再次启动或重复发送")
    validate_stage_gate(run_root, mode)
    return baseline, mode_dir, repo, prompt


def validate_stage_gate(run_root: Path, mode: str) -> None:
    result_path = run_root / "EXPERIMENT_RESULT.json"
    if mode == "no-skill":
        if result_path.is_file():
            status = str(read_json(result_path).get("status", ""))
            if status in {
                "ready_for_with_skill",
                "needs_task_hardening",
                "needs_skill_revision",
                "passed",
            }:
                raise ValueError(f"当前实验状态为 {status}，不得再次启动 no-skill")
        return
    if not result_path.is_file():
        raise ValueError("no-skill 尚未判分，不能启动 with-skill")
    result = read_json(result_path)
    if result.get("status") != "ready_for_with_skill":
        raise ValueError(
            "只有 ready_for_with_skill 状态才能启动 with-skill："
            f"{result.get('status')}"
        )
    no_skill = result.get("no_skill")
    if not isinstance(no_skill, dict) or int(no_skill.get("reward", 1)) != 0:
        raise ValueError("no-skill 没有得到有效 reward=0，不能启动 with-skill")
    agent = no_skill.get("agent")
    if not isinstance(agent, dict) or not (
        agent.get("monitor_status") == "stopped"
        and agent.get("completion_confirmed") is True
    ):
        raise ValueError("no-skill 尚未确认完成并停止监听器，不能启动 with-skill")


def resolve_cli(explicit: Path | None) -> Path:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit.expanduser())
    env_cli = os.environ.get("TRAE_CN_CLI", "").strip()
    if env_cli:
        candidates.append(Path(env_cli).expanduser())
    path_cli = shutil.which("trae-cn")
    if path_cli:
        candidates.append(Path(path_cli))
    candidates.extend(
        [
            Path("/Applications/Trae CN.app/Contents/Resources/app/bin/trae-cn"),
            Path.home()
            / "Applications/Trae CN.app/Contents/Resources/app/bin/trae-cn",
        ]
    )
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise ValueError(
        "找不到 Trae CN CLI。可设置 TRAE_CN_CLI，或确认 "
        "/Applications/Trae CN.app 已安装"
    )


def workspace_path_from_json(path: Path) -> Path | None:
    try:
        value = read_json(path).get("folder")
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, str) or not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme != "file":
        return None
    return Path(unquote(parsed.path)).resolve()


def find_workspace_ids(storage_root: Path, repo: Path) -> list[str]:
    if not storage_root.is_dir():
        return []
    matches: list[str] = []
    for workspace_file in storage_root.glob("*/workspace.json"):
        if workspace_path_from_json(workspace_file) == repo:
            matches.append(workspace_file.parent.name)
    return sorted(set(matches))


def stage_payload(
    baseline: dict,
    run_root: Path,
    mode: str,
    mode_dir: Path,
    repo: Path,
    prompt: Path,
    cli: Path,
    storage_root: Path,
) -> dict:
    return {
        "version": 1,
        "task_id": baseline.get("task_id"),
        "run_root": str(run_root),
        "mode": mode,
        "mode_dir": str(mode_dir),
        "repo": str(repo),
        "prompt": str(prompt),
        "prompt_sha256": sha256(prompt),
        "expected_model": baseline.get("expected_model"),
        "trae_app": "Trae CN",
        "trae_cli": str(cli),
        "workspace_storage_root": str(storage_root),
        "launch_record": str(mode_dir / "TRAE_LAUNCH.json"),
    }


def identify_workspace(storage_root: Path, repo: Path, wait_seconds: float) -> str:
    deadline = time.monotonic() + max(wait_seconds, 0.0)
    while True:
        matches = find_workspace_ids(storage_root, repo)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                "同一 repo 对应多个 workspaceStorage 标识，无法安全绑定："
                + ", ".join(matches)
            )
        if time.monotonic() >= deadline:
            raise ValueError("Trae 已收到打开请求，但尚未生成可核对的 workspaceStorage 标识")
        time.sleep(0.5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "launch", "adopt"))
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("no-skill", "with-skill"), required=True)
    parser.add_argument("--cli", type=Path)
    parser.add_argument(
        "--workspace-storage-root",
        type=Path,
        default=Path.home()
        / "Library/Application Support/Trae CN/User/workspaceStorage",
    )
    parser.add_argument("--wait-seconds", type=float, default=60.0)
    parser.add_argument("--formal-run-confirmed", action="store_true")
    parser.add_argument("--existing-window-confirmed", action="store_true")
    args = parser.parse_args()

    try:
        run_root = args.run_root.expanduser().resolve()
        baseline, mode_dir, repo, prompt = load_stage(run_root, args.mode)
        cli = resolve_cli(args.cli)
        storage_root = args.workspace_storage_root.expanduser().resolve()
        payload = stage_payload(
            baseline,
            run_root,
            args.mode,
            mode_dir,
            repo,
            prompt,
            cli,
            storage_root,
        )
        launch_path = mode_dir / "TRAE_LAUNCH.json"
        if args.action == "inspect":
            payload["status"] = "ready_to_launch"
            payload["existing_launch_record"] = (
                read_json(launch_path) if launch_path.is_file() else None
            )
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        if not args.formal_run_confirmed:
            raise ValueError("正式跑题时必须传入 --formal-run-confirmed")
        resume_identification = False
        if launch_path.is_file():
            existing = read_json(launch_path)
            if (
                existing.get("repo") == str(repo)
                and existing.get("prompt_sha256") == sha256(prompt)
                and existing.get("status") == "window_identified"
            ):
                print(json.dumps(existing, ensure_ascii=False, indent=2))
                return 0
            if (
                existing.get("repo") == str(repo)
                and existing.get("prompt_sha256") == sha256(prompt)
                and existing.get("status")
                in {"launching", "adopting", "window_identification_failed"}
            ):
                payload = existing
                resume_identification = True
            else:
                raise ValueError(
                    f"该阶段已有失败或不一致的启动记录，禁止自动重复开窗：{launch_path}"
                )

        if args.action == "adopt" and not args.existing_window_confirmed:
            raise ValueError("接管既有窗口时必须传入 --existing-window-confirmed")

        if not resume_identification:
            payload.update(
                {
                    "status": "launching" if args.action == "launch" else "adopting",
                    "launch_method": (
                        "trae-cn-new-window"
                        if args.action == "launch"
                        else "existing-window-adopted"
                    ),
                    "created_at": now(),
                }
            )
            write_json(launch_path, payload)

        if args.action == "launch" and not resume_identification:
            completed = subprocess.run(
                [str(cli), "--new-window", str(repo)],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            payload["cli_exit_code"] = completed.returncode
            payload["cli_stdout"] = completed.stdout.strip()
            payload["cli_stderr"] = completed.stderr.strip()
            payload["launch_requested_at"] = now()
            if completed.returncode != 0:
                payload["status"] = "launch_failed"
                write_json(launch_path, payload)
                raise ValueError(
                    "Trae CLI 打开工作区失败："
                    + (completed.stderr.strip() or f"exit={completed.returncode}")
                )

        try:
            workspace_id = identify_workspace(storage_root, repo, args.wait_seconds)
        except ValueError:
            payload["status"] = "window_identification_failed"
            payload["identification_failed_at"] = now()
            write_json(launch_path, payload)
            raise
        payload.update(
            {
                "status": "window_identified",
                "workspace_storage_id": workspace_id,
                "window_binding_id": f"workspaceStorage:{workspace_id}",
                "identified_at": now(),
                "next_action": (
                    "在当前执行线程中读取 Trae CN 这个精确窗口的结构化状态，核对 repo 和模型，"
                    "只通过 accessibility、DOM 或 structured-api 定位 role=textbox 的 Agent 文本 composer，"
                    "排除中文、English、语言、输入法、keyboard、IME、语音、麦克风、录音、波形、计时等节点后直接设置其值；"
                    "如果出现波形、录音计时或绿色确认按钮，立即失败，不点击确认；"
                    "不点击输入框、不移动鼠标、不用 Tab、快捷键或剪贴板；仅点击同一 composer 内唯一的发送提示词按钮一次。"
                    "发送后不得中断、停止、取消、重试、补发消息、点击任何控件或关闭窗口，只读等待正常最终回复。"
                ),
            }
        )
        write_json(launch_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
