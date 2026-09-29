#!/usr/bin/env python3
"""Bind existing Trae windows and grade sequential no-skill/with-skill runs."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


READY_FOR_WITH_SKILL = 10
TASK_TOO_EASY = 20
SKILL_NEEDS_REVISION = 21
INFRASTRUCTURE_ERROR = 22
ALLOWED_COMPOSER_LOCATORS = {"accessibility", "dom", "structured-api"}
FORBIDDEN_LANGUAGE_TERMS = (
    "中文",
    "中",
    "english",
    "英文",
    "英",
    "语言",
    "输入法",
    "keyboard",
    "ime",
    "切换输入法",
)
FORBIDDEN_VOICE_TERMS = (
    "语音",
    "voice",
    "microphone",
    "mic",
    "麦克风",
    "录音",
    "recording",
    "waveform",
    "波形",
    "duration",
    "计时",
)
FORBIDDEN_SEND_TERMS = (
    "停止",
    "取消",
    "重试",
    "授权",
    "模型",
    "language",
    "keyboard",
    "ime",
)


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prior_experiment(run_root: Path) -> dict | None:
    path = run_root / "EXPERIMENT_RESULT.json"
    return read_json(path) if path.is_file() else None


def infrastructure_result(
    run_root: Path, mode: str, message: str, **details: object
) -> dict:
    result: dict = {
        "status": "infrastructure_error",
        "message": message,
        "mode": mode,
        **details,
    }
    previous = prior_experiment(run_root)
    if mode == "with-skill" and previous:
        if isinstance(previous.get("no_skill"), dict):
            result["no_skill"] = previous["no_skill"]
            result["no_skill_source"] = previous.get("no_skill_source")
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def load_context(args: argparse.Namespace) -> tuple[dict, Path, Path, Path]:
    run_root = args.run_root.expanduser().resolve()
    task_dir = args.task_dir.expanduser().resolve()
    baseline_path = run_root / "BASELINE.json"
    if not baseline_path.is_file():
        raise ValueError(f"缺少 BASELINE.json：{baseline_path}")
    baseline = read_json(baseline_path)
    mode_dir_name = baseline.get("mode_dirs", {}).get(args.mode)
    if not mode_dir_name:
        raise ValueError(f"BASELINE.json 缺少 {args.mode} 目录映射")
    mode_dir = run_root / mode_dir_name
    return baseline, task_dir, run_root, mode_dir


def git(repo: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=repo, text=True, capture_output=True, check=check
    )


def repo_path(baseline: dict, mode_dir: Path, mode: str | None = None) -> Path:
    repo_dir_names = baseline.get("repo_dir_names")
    repo_dir_name = repo_dir_names.get(mode) if isinstance(repo_dir_names, dict) else None
    # 兼容改名之前已经生成的运行目录。
    if not repo_dir_name:
        repo_dir_name = baseline.get("repo_dir_name")
    if not isinstance(repo_dir_name, str) or not repo_dir_name:
        raise ValueError("BASELINE.json 缺少当前模式的仓库目录名")
    return mode_dir / repo_dir_name


def monitor_request_path(mode_dir: Path) -> Path:
    return mode_dir / "MONITOR_REQUEST.json"


def validate_experiment_inputs(baseline: dict, task_dir: Path, run_root: Path) -> None:
    mode_dirs = baseline.get("mode_dirs", {})
    no_skill_dir = run_root / str(mode_dirs.get("no-skill", ""))
    with_skill_dir = run_root / str(mode_dirs.get("with-skill", ""))
    no_skill_prompt = no_skill_dir / "PROMPT.md"
    with_skill_prompt = with_skill_dir / "PROMPT.md"
    if not no_skill_prompt.is_file() or not with_skill_prompt.is_file():
        raise ValueError("no-skill 或 with-skill 提示词缺失")
    no_skill_prompt_sha = sha256(no_skill_prompt)
    with_skill_prompt_sha = sha256(with_skill_prompt)
    if no_skill_prompt_sha != baseline.get("no_skill_prompt_sha256"):
        raise ValueError("no-skill 提示词散列与 BASELINE.json 不一致")
    if with_skill_prompt_sha != baseline.get("with_skill_prompt_sha256"):
        raise ValueError("with-skill 提示词散列与 BASELINE.json 不一致")
    if no_skill_prompt_sha == with_skill_prompt_sha or baseline.get("prompts_identical"):
        raise ValueError("with-skill 提示词必须额外包含专家解题思路")
    if not baseline.get("task_contract_identical"):
        raise ValueError("BASELINE.json 未确认两侧使用同一题目契约")

    no_skill_repo = repo_path(baseline, no_skill_dir, "no-skill")
    with_skill_repo = repo_path(baseline, with_skill_dir, "with-skill")
    if (no_skill_repo / ".trae/skills").exists() or (
        with_skill_repo / ".trae/skills"
    ).exists():
        raise ValueError("两侧都不得通过 Trae 项目级 skill 注入专家经验")
    if baseline.get("with_skill_delivery") != "prompt-context":
        raise ValueError("with-skill 必须通过提示词上下文提供专家解题思路")
    formal_skill = task_dir / "sources/skill/SKILL.md"
    if not formal_skill.is_file() or sha256(formal_skill) != baseline.get("skill_sha256"):
        raise ValueError("正式包中的专家 SKILL.md 与准备运行时不一致")
    if git(no_skill_repo, "rev-parse", "HEAD").stdout.strip() != baseline.get(
        "baseline_head"
    ):
        raise ValueError("no-skill 工作区 HEAD 与基线不一致")
    if git(with_skill_repo, "rev-parse", "HEAD").stdout.strip() != baseline.get(
        "baseline_head"
    ):
        raise ValueError("with-skill 工作区 HEAD 与基线不一致")


def bind_existing_window(args: argparse.Namespace) -> int:
    baseline, task_dir, run_root, mode_dir = load_context(args)
    validate_experiment_inputs(baseline, task_dir, run_root)
    if not args.existing_window_confirmed:
        raise ValueError("必须先确认目标题目的 Trae 窗口已经存在，再登记运行")
    if not args.prompt_submitted_confirmed:
        raise ValueError("必须确认提示词已发送到绑定窗口，再登记 submitted")
    if not args.prompt_visible_in_chat_confirmed:
        raise ValueError("必须确认完整用户消息已出现在绑定窗口的对话记录中")
    if not args.agent_started_confirmed:
        raise ValueError("必须确认 Agent 已开始回复、思考、读取文件或调用工具")
    if not args.window_binding_id.strip():
        raise ValueError("必须提供唯一且稳定的 --window-binding-id")
    if args.window_workspace_path is None:
        raise ValueError("必须提供窗口报告的 --window-workspace-path")
    if not args.model_confirmed:
        raise ValueError("必须确认绑定窗口使用指定模型，再传入 --model-confirmed")
    if args.composer_locator_type not in ALLOWED_COMPOSER_LOCATORS:
        raise ValueError(
            "Agent 编辑器只能通过 accessibility、dom 或 structured-api 定位；"
            "坐标、截图、前台窗口和模糊文本匹配均不允许"
        )
    if args.composer_role != "textbox":
        raise ValueError("绑定的 Agent 编辑器 role 必须是 textbox")
    if args.send_locator_type not in ALLOWED_COMPOSER_LOCATORS:
        raise ValueError(
            "发送按钮只能通过 accessibility、dom 或 structured-api 定位"
        )
    if args.send_role != "button":
        raise ValueError("绑定的发送控件 role 必须是 button")
    if not args.composer_value_written_confirmed:
        raise ValueError("必须确认完整 PROMPT.md 已直接写入 Agent 编辑器值")
    if not args.send_button_identified_confirmed:
        raise ValueError("必须确认发送按钮已在同一个 Agent composer 内唯一识别")
    if not args.same_composer_scope_confirmed:
        raise ValueError("必须确认编辑器和发送按钮属于同一个 Agent composer")
    if not args.language_controls_rejected_confirmed:
        raise ValueError("必须确认已排除语言和输入法控件，不能把它们当作编辑器或发送按钮")
    if not args.voice_input_mode_rejected_confirmed:
        raise ValueError("必须确认当前不是语音输入/录音状态，不能把波形、计时或绿色确认按钮当作文本发送")
    if not args.text_composer_visible_confirmed:
        raise ValueError("必须确认可见的是文本消息编辑器，而不是语音录音条")
    if not args.no_mouse_movement_confirmed:
        raise ValueError("必须确认提交过程中没有移动鼠标、光标或输入焦点")
    if args.non_send_clicks != 0:
        raise ValueError("提交过程中除最后一次发送按钮点击外不得点击其他控件")
    if not args.composer_name.strip() or not args.send_name.strip():
        raise ValueError("必须提供结构化接口返回的编辑器名称和发送按钮名称")
    control_names = " ".join((args.composer_name, args.send_name)).casefold()
    if any(term.casefold() in control_names for term in FORBIDDEN_LANGUAGE_TERMS):
        raise ValueError("编辑器或发送按钮名称命中了语言/输入法控件，拒绝登记")
    if any(term.casefold() in control_names for term in FORBIDDEN_VOICE_TERMS):
        raise ValueError("编辑器或发送按钮名称命中了语音/录音控件，拒绝登记")
    send_name = args.send_name.casefold().strip()
    if not any(token in send_name for token in ("发送", "send")):
        raise ValueError("发送按钮名称必须明确包含发送语义，例如‘发送提示词’或 Send")
    if any(term.casefold() in send_name for term in FORBIDDEN_SEND_TERMS):
        raise ValueError("发送按钮名称命中了停止、取消、授权、语言或模型控件，拒绝登记")
    result_path = run_root / "EXPERIMENT_RESULT.json"
    if args.mode == "with-skill":
        if not result_path.is_file():
            raise ValueError("no-skill 尚未判分，不能启动 with-skill")
        result = read_json(result_path)
        if result.get("status") != "ready_for_with_skill":
            raise ValueError(
                "实验状态不是 ready_for_with_skill，不能启动 with-skill："
                f"{result.get('status')}"
            )
        no_skill = result.get("no_skill", {})
        if no_skill.get("status") != "completed" or int(no_skill.get("reward", 1)) != 0:
            raise ValueError("只有 no-skill 正常完成且 reward=0 后才能启动 with-skill")
        no_skill_agent = no_skill.get("agent", {})
        if not isinstance(no_skill_agent, dict) or not (
            no_skill_agent.get("monitor_status") == "stopped"
            and no_skill_agent.get("completion_confirmed") is True
        ):
            raise ValueError("no-skill 未确认正常完成并停止监听器，不能启动 with-skill")
        previous_window_id = str(no_skill_agent.get("window_binding_id", "")).strip()
        if previous_window_id and args.window_binding_id.strip() == previous_window_id:
            raise ValueError("with-skill 必须使用新窗口，不能复用 no-skill 的窗口标识")
        prior_with_skill_window_id = str(
            baseline.get("prior_with_skill_window_binding_id", "")
        ).strip()
        if prior_with_skill_window_id and (
            args.window_binding_id.strip() == prior_with_skill_window_id
        ):
            raise ValueError("skill 返修必须使用新的 with-skill 窗口，不能复用上一轮窗口")
    elif result_path.is_file():
        result = read_json(result_path)
        if result.get("status") == "ready_for_with_skill":
            raise ValueError("当前运行目录已复用有效 no-skill 证据，不得再次提交 no-skill")
    state_path = mode_dir / "TRAE_RUN.json"
    if state_path.exists():
        raise ValueError(f"该工作区已有 Trae 运行记录，拒绝重复提交：{state_path}")
    repo = repo_path(baseline, mode_dir, args.mode)
    prompt_path = mode_dir / "PROMPT.md"
    if not repo.is_dir() or not prompt_path.is_file():
        raise ValueError(f"Trae 工作区材料不完整：{mode_dir}")
    launch_path = mode_dir / "TRAE_LAUNCH.json"
    if not launch_path.is_file():
        raise ValueError(
            "缺少 TRAE_LAUNCH.json。必须先用 launch_trae_stage.py 精确启动或接管窗口，"
            "再在同一执行线程中发送提示词"
        )
    launch = read_json(launch_path)
    if launch.get("status") != "window_identified":
        raise ValueError(
            f"Trae 窗口尚未完成稳定绑定：{launch.get('status')}"
        )
    if Path(str(launch.get("repo", ""))).expanduser().resolve() != repo.resolve():
        raise ValueError("TRAE_LAUNCH.json 中的 repo 与本轮目标不一致")
    if launch.get("prompt_sha256") != sha256(prompt_path):
        raise ValueError("TRAE_LAUNCH.json 中的提示词散列与当前 PROMPT.md 不一致")
    if launch.get("window_binding_id") != args.window_binding_id.strip():
        raise ValueError("bind 使用的窗口标识与 TRAE_LAUNCH.json 不一致")
    reported_workspace = args.window_workspace_path.expanduser().resolve()
    if reported_workspace != repo.resolve():
        raise ValueError(
            "绑定窗口的工作区路径与本轮目标不一致："
            f"窗口={reported_workspace}，目标={repo.resolve()}"
        )
    started = now()
    monitor_path = monitor_request_path(mode_dir)
    monitor_name = (
        f"OBM Trae {baseline.get('task_id')} {run_root.name} {args.mode} 监听器"
    )
    monitor_prompt = (
        f"每 15 分钟检查 Trae CN 中 OBM 题目 {baseline.get('task_id')} 的 "
        f"{args.mode} Agent 运行。唯一窗口绑定标识是 {args.window_binding_id}，"
        f"对应工作区是 {repo}，运行记录是 {state_path}。"
        "监听期间禁止执行任何 Trae 可执行文件或界面接口。不得运行 trae-cn 的任何子命令，"
        "trae-cn --status 也禁止；不得执行 Trae 应用包内的 Electron、CLI 或辅助程序，不得使用 open -a、"
        "AppleScript、界面自动化、窗口选择、截图激活或可访问性操作访问 Trae。"
        "只能读取该绑定标识对应的 TRAE_RUN.json、MONITOR_REQUEST.json、workspaceStorage 文件、日志、SQLite 数据库"
        "以及操作系统进程表，读取时不得启动或激活 Trae。"
        "不得移动鼠标指针、文本光标或选区，不得点击、滚动、切换窗口或标签页，不得抢占用户输入焦点。"
        "监听器不得尝试定位或修复 Agent 编辑器，不得点击语言、输入法、发送或任何其他控件。"
        "提示词发送后到正常最终回复出现前属于不可干预期。不得中断、停止、取消、暂停、重试或继续 Agent，"
        "不得点击停止、取消、重试、继续、批准、拒绝、新建对话、切换会话、清空上下文、关闭窗口或任何其他控件，"
        "不得向输入框写入第二条消息、补充说明、催促、确认、授权答复或发送快捷键。"
        "Agent 请求授权或提出问题时只通知用户，不代替用户操作 Trae，也不把用户在其他地方的回复写回对话。"
        "监听器不是启动器；如果现有材料无法确认状态，把监听状态改为 failed 或 stopped，等待用户明确恢复正式跑题。"
        "只根据绑定窗口标识对应的现有日志和状态数据判断。明确记录 Agent 已正常结束并给出最终回复时，"
        "立即暂停或删除本 heartbeat，并把监听状态登记为 stopped。确认 automation 不再是 ACTIVE 后，"
        "使用 monitor --status stopped --completion-confirmed 保存完成证据。此后执行线程可以关闭这个精确绑定的窗口，"
        "再运行独立 grade --confirmed-complete；不得使用 completing 状态继续轮询，也不得先判分再关闭监听器。"
        "如果仍在思考、执行命令、等待工具，或者无法确认是否结束，保持安静并等待下一次检查；"
        "不要因为 CLI 已返回、Git 出现改动或等待时间较长就判定完成。"
        "如果需要用户授权或 Agent 提出问题，只通知用户；Trae 崩溃、模型不可用或出现基础设施错误时也通知用户。"
        "本监听器停止后按实验状态机继续：no-skill 只有 reward=0 才能启动 with-skill；"
        "with-skill 完成后按 verifier 结果继续返修或完成流程。"
    )
    monitor = {
        "version": 1,
        "status": "pending_creation",
        "kind": "codex-thread-heartbeat",
        "automation_name": monitor_name,
        "automation_prompt": monitor_prompt,
        "task_id": baseline.get("task_id"),
        "mode": args.mode,
        "interval_minutes": 15,
        "quiet_when_unchanged": True,
        "task_dir": str(task_dir),
        "run_root": str(run_root),
        "mode_dir": str(mode_dir),
        "repo": str(repo),
        "workspace_scope": "single-current-mode",
        "window_binding_id": args.window_binding_id,
        "window_workspace_path": str(reported_workspace),
        "cursor_policy": "read-only; do not move pointer, caret, selection, or input focus",
        "reopen_policy": "never launch or reopen Trae from heartbeat",
        "command_policy": "never execute trae-cn, including --status, or any Trae application binary from heartbeat",
        "allowed_monitor_sources": [
            "existing run records",
            "existing workspaceStorage files and SQLite databases",
            "existing logs",
            "operating-system process table",
        ],
        "stop_policy": "stop heartbeat immediately when the current Agent run completes, before grading",
        "trae_run": str(state_path),
        "completion_rule": "只在绑定窗口对应的既有日志或状态记录明确表明 Agent 正常结束并给出最终回复后判分；代码变动或进程存在不代表完成。",
        "created_at": now(),
    }
    write_json(monitor_path, monitor)
    state = {
        "mode": args.mode,
        "status": "submitted",
        "submitted_at": started,
        "cli_returned_at": None,
        "trae_cli": None,
        "expected_model": baseline.get("expected_model"),
        "model_confirmed_before_submission": True,
        "existing_window_confirmed": True,
        "prompt_submitted_confirmed": True,
        "prompt_visible_in_chat_confirmed": True,
        "agent_started_confirmed": True,
        "window_binding_id": args.window_binding_id,
        "window_workspace_path": str(reported_workspace),
        "prompt": str(prompt_path),
        "prompt_sha256": sha256(prompt_path),
        "repo": str(repo),
        "monitoring": {
            "preferred": True,
            "required_for_grade": False,
            "request": str(monitor_path),
            "status": monitor["status"],
            "interval_minutes": 15,
            "quiet_when_unchanged": True,
        },
        "submission_method": "bound-trae-window-agent-chat",
        "launch_record": str(launch_path),
        "launch_method": launch.get("launch_method"),
        "submission_evidence": {
            "send_triggered": True,
            "full_user_message_visible_in_chat": True,
            "agent_started": True,
            "composer": {
                "locator_type": args.composer_locator_type,
                "role": args.composer_role,
                "name": args.composer_name,
                "value_written_directly": True,
            },
            "send_button": {
                "locator_type": args.send_locator_type,
                "role": args.send_role,
                "name": args.send_name,
                "same_composer_scope": True,
                "click_count": 1,
            },
            "language_controls_rejected": True,
            "voice_input_mode_rejected": True,
            "text_composer_visible": True,
            "mouse_movement": False,
            "non_send_clicks": 0,
        },
        "completion_semantics": "运行记录只绑定既有窗口；必须由该窗口对应的既有日志或状态记录确认 Agent 正常结束后再判分。",
    }
    write_json(state_path, state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def record_monitor(args: argparse.Namespace) -> int:
    _, _, _, mode_dir = load_context(args)
    state_path = mode_dir / "TRAE_RUN.json"
    request_path = monitor_request_path(mode_dir)
    if not state_path.is_file() or not request_path.is_file():
        raise ValueError("Trae 尚未成功提交，不能登记监听器")
    state = read_json(state_path)
    request = read_json(request_path)
    if request.get("status") == "stopped":
        if args.status == "stopped" and args.completion_confirmed:
            print(json.dumps(state.get("monitoring", {}), ensure_ascii=False, indent=2))
            return 0
        raise ValueError("该轮监听器已经确认完成并停止，不能重新激活或改写状态")
    if state.get("status") != "submitted":
        raise ValueError(f"Trae 运行状态不是 submitted，不能改写监听器：{state.get('status')}")
    evidence = state.get("submission_evidence", {})
    if args.status == "active" and not (
        state.get("status") == "submitted"
        and state.get("prompt_submitted_confirmed") is True
        and state.get("prompt_visible_in_chat_confirmed") is True
        and state.get("agent_started_confirmed") is True
        and evidence.get("send_triggered") is True
        and evidence.get("full_user_message_visible_in_chat") is True
        and evidence.get("agent_started") is True
    ):
        raise ValueError("提示词未确认发送并启动 Agent，不能启用监听器")
    if args.status == "active" and not args.automation_id:
        raise ValueError("监听器启用时必须记录 automation id")
    if args.status == "stopped" and not args.completion_confirmed:
        raise ValueError("停止完成后的监听器时必须传入 --completion-confirmed")
    if args.status != "stopped" and args.completion_confirmed:
        raise ValueError("--completion-confirmed 只能与 --status stopped 一起使用")
    request["status"] = args.status
    request["updated_at"] = now()
    if args.status == "stopped":
        request["completion_confirmed"] = True
        request["completion_confirmed_at"] = request["updated_at"]
        request["window_may_close"] = True
    else:
        request["completion_confirmed"] = False
        request["window_may_close"] = False
    if args.automation_id:
        request["automation_id"] = args.automation_id
    if args.automation_name:
        request["automation_name"] = args.automation_name
    write_json(request_path, request)
    state["monitoring"] = {
        "preferred": True,
        "required_for_grade": False,
        "request": str(request_path),
        "status": args.status,
        "interval_minutes": int(request.get("interval_minutes", 15)),
        "quiet_when_unchanged": True,
        "automation_id": request.get("automation_id"),
        "automation_name": request.get("automation_name"),
        "completion_confirmed": request.get("completion_confirmed", False),
        "completion_confirmed_at": request.get("completion_confirmed_at"),
    }
    state["window_may_close"] = bool(request.get("window_may_close", False))
    write_json(state_path, state)
    print(json.dumps(state["monitoring"], ensure_ascii=False, indent=2))
    return 0


def read_monitor_context(mode_dir: Path) -> dict:
    request_path = monitor_request_path(mode_dir)
    if not request_path.is_file():
        return {
            "status": "not_configured",
            "automation_id": None,
            "interval_minutes": None,
        }
    monitor = read_json(request_path)
    return monitor


def create_patch(repo: Path, baseline_head: str, patch_path: Path) -> None:
    git(repo, "add", "-N", "--all")
    try:
        patch = git(repo, "diff", "--binary", baseline_head, "--").stdout
        patch_path.write_text(patch, encoding="utf-8")
    finally:
        git(repo, "reset", "--mixed", "--quiet", "HEAD", check=False)


def grade(args: argparse.Namespace) -> int:
    baseline, task_dir, run_root, mode_dir = load_context(args)
    validate_experiment_inputs(baseline, task_dir, run_root)
    monitor = read_monitor_context(mode_dir)
    if not args.confirmed_complete:
        raise ValueError("必须先从绑定窗口对应的既有日志或状态记录确认 Agent 已正常结束，再传入 --confirmed-complete")
    if not (
        monitor.get("status") == "stopped"
        and monitor.get("completion_confirmed") is True
    ):
        raise ValueError(
            "Agent 正常完成后必须先停止对应监听器，并用 --completion-confirmed 保存完成证据"
        )
    state_path = mode_dir / "TRAE_RUN.json"
    if not state_path.is_file():
        raise ValueError("找不到 Trae 提交记录，不能判分")
    state = read_json(state_path)
    if state.get("status") != "submitted":
        raise ValueError(f"Trae 运行状态不是 submitted：{state.get('status')}")
    repo = repo_path(baseline, mode_dir, args.mode)
    output = mode_dir / "trae-output"
    verification = mode_dir / "verification"
    if output.exists() or verification.exists():
        raise ValueError("该工作区已有回收或验证结果，拒绝覆盖")
    output.mkdir()
    patch_path = output / "model.patch"
    create_patch(repo, str(baseline["baseline_head"]), patch_path)
    verifier = Path(__file__).with_name("verify_agent_patch.py")
    checked = subprocess.run(
        [
            sys.executable,
            str(verifier),
            "--task-dir",
            str(task_dir),
            "--patch",
            str(patch_path),
            "--output-dir",
            str(verification),
            "--docker",
            args.docker,
        ],
        text=True,
    )
    verification_path = verification / "VERIFICATION.json"
    if not verification_path.is_file():
        payload = infrastructure_result(
            run_root,
            args.mode,
            "verifier 未生成 VERIFICATION.json",
            exit_code=checked.returncode,
        )
        write_json(run_root / "EXPERIMENT_RESULT.json", payload)
        return INFRASTRUCTURE_ERROR
    scored = read_json(verification_path)
    if scored.get("status") != "completed" or scored.get("reward") not in (0, 1):
        payload = infrastructure_result(
            run_root,
            args.mode,
            "Trae 工作区未得到可用的二元 verifier 结果",
            verification=scored,
        )
        write_json(run_root / "EXPERIMENT_RESULT.json", payload)
        return INFRASTRUCTURE_ERROR
    scored["agent"] = {
        "runner": "Trae CN",
        "expected_model": baseline.get("expected_model"),
        "submitted_at": state.get("submitted_at"),
        "confirmed_complete_at": now(),
        "prompt_sha256": state.get("prompt_sha256"),
        "patch_sha256": sha256(patch_path),
        "workspace": str(repo),
        "window_binding_id": state.get("window_binding_id"),
        "window_workspace_path": state.get("window_workspace_path"),
        "completion_confirmation": "explicit --confirmed-complete from bound-window logs or state records",
        "monitor_status": monitor.get("status"),
        "completion_confirmed": monitor.get("completion_confirmed") is True,
        "completion_confirmed_at": monitor.get("completion_confirmed_at"),
        "monitor_automation_id": monitor.get("automation_id"),
        "monitor_interval_minutes": monitor.get("interval_minutes"),
    }
    state["status"] = "graded"
    state["confirmed_complete_at"] = scored["agent"]["confirmed_complete_at"]
    state["reward"] = scored["reward"]
    state["patch"] = str(patch_path)
    state["verification"] = str(verification_path)
    write_json(state_path, state)

    result_path = run_root / "EXPERIMENT_RESULT.json"
    if args.mode == "no-skill":
        if int(scored["reward"]) == 1:
            result = {
                "status": "needs_task_hardening",
                "message": "no-skill 已通过。停止，不运行 with-skill；需要提高题目真实推理难度。",
                "no_skill": scored,
                "no_skill_source": str(mode_dir),
            }
            exit_code = TASK_TOO_EASY
        else:
            result = {
                "status": "ready_for_with_skill",
                "message": "no-skill 正常完成且 reward=0，可以启动 with-skill。",
                "no_skill": scored,
                "no_skill_source": str(mode_dir),
            }
            exit_code = READY_FOR_WITH_SKILL
    else:
        if not result_path.is_file():
            raise ValueError("缺少 no-skill 判分结果")
        previous = read_json(result_path)
        no_skill = previous.get("no_skill")
        if not isinstance(no_skill, dict) or int(no_skill.get("reward", 1)) != 0:
            raise ValueError("no-skill 证据无效，不能写入 with-skill 结果")
        if int(scored["reward"]) == 0:
            result = {
                "status": "needs_skill_revision",
                "message": "no-skill 失败且 with-skill 也失败，需要返修中文专家 skill。",
                "no_skill": no_skill,
                "no_skill_source": previous.get("no_skill_source"),
                "with_skill": scored,
            }
            exit_code = SKILL_NEEDS_REVISION
        else:
            result = {
                "status": "passed",
                "message": "有效对照：no-skill reward=0，with-skill reward=1。",
                "no_skill": no_skill,
                "no_skill_source": previous.get("no_skill_source"),
                "with_skill": scored,
            }
            exit_code = 0
    write_json(result_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


def status(args: argparse.Namespace) -> int:
    baseline, _, run_root, mode_dir = load_context(args)
    monitor_path = monitor_request_path(mode_dir)
    launch_path = mode_dir / "TRAE_LAUNCH.json"
    payload = {
        "task_id": baseline.get("task_id"),
        "mode": args.mode,
        "mode_dir": str(mode_dir),
        "launch": read_json(launch_path) if launch_path.is_file() else None,
        "trae_run": read_json(mode_dir / "TRAE_RUN.json") if (mode_dir / "TRAE_RUN.json").is_file() else None,
        "monitor": read_json(monitor_path) if monitor_path.is_file() else None,
        "experiment": read_json(run_root / "EXPERIMENT_RESULT.json") if (run_root / "EXPERIMENT_RESULT.json").is_file() else None,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--task-dir", type=Path, required=True)
    common.add_argument("--run-root", type=Path, required=True)
    common.add_argument("--mode", choices=("no-skill", "with-skill"), required=True)

    bind_parser = sub.add_parser("bind", parents=[common])
    bind_parser.add_argument("--existing-window-confirmed", action="store_true")
    bind_parser.add_argument("--prompt-submitted-confirmed", action="store_true")
    bind_parser.add_argument("--prompt-visible-in-chat-confirmed", action="store_true")
    bind_parser.add_argument("--agent-started-confirmed", action="store_true")
    bind_parser.add_argument("--window-binding-id", required=True)
    bind_parser.add_argument("--window-workspace-path", type=Path, required=True)
    bind_parser.add_argument("--model-confirmed", action="store_true")
    bind_parser.add_argument(
        "--composer-locator-type",
        choices=sorted(ALLOWED_COMPOSER_LOCATORS),
        required=True,
    )
    bind_parser.add_argument("--composer-role", required=True)
    bind_parser.add_argument("--composer-name", required=True)
    bind_parser.add_argument(
        "--send-locator-type",
        choices=sorted(ALLOWED_COMPOSER_LOCATORS),
        required=True,
    )
    bind_parser.add_argument("--send-role", required=True)
    bind_parser.add_argument("--send-name", required=True)
    bind_parser.add_argument("--composer-value-written-confirmed", action="store_true")
    bind_parser.add_argument("--send-button-identified-confirmed", action="store_true")
    bind_parser.add_argument("--same-composer-scope-confirmed", action="store_true")
    bind_parser.add_argument(
        "--language-controls-rejected-confirmed", action="store_true"
    )
    bind_parser.add_argument(
        "--voice-input-mode-rejected-confirmed", action="store_true"
    )
    bind_parser.add_argument(
        "--text-composer-visible-confirmed", action="store_true"
    )
    bind_parser.add_argument("--no-mouse-movement-confirmed", action="store_true")
    bind_parser.add_argument("--non-send-clicks", type=int, required=True)
    bind_parser.set_defaults(func=bind_existing_window)

    grade_parser = sub.add_parser("grade", parents=[common])
    grade_parser.add_argument("--confirmed-complete", action="store_true")
    grade_parser.add_argument("--docker", default="docker")
    grade_parser.set_defaults(func=grade)

    status_parser = sub.add_parser("status", parents=[common])
    status_parser.set_defaults(func=status)

    monitor_parser = sub.add_parser("monitor", parents=[common])
    monitor_parser.add_argument(
        "--status",
        choices=("active", "stopped", "failed"),
        required=True,
    )
    monitor_parser.add_argument("--automation-id")
    monitor_parser.add_argument("--automation-name")
    monitor_parser.add_argument("--completion-confirmed", action="store_true")
    monitor_parser.set_defaults(func=record_monitor)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    return INFRASTRUCTURE_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
