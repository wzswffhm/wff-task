#!/usr/bin/env python3
"""Grade a user-run Trae workspace without window binding or heartbeat files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from run_trae_experiment import (
    SKILL_NEEDS_REVISION,
    TASK_TOO_EASY,
    validate_experiment_inputs,
    create_patch,
    git,
    infrastructure_result,
    load_context,
    now,
    read_json,
    repo_path,
    sha256,
    write_json,
)


READY_FOR_WITH_SKILL = 10
INFRASTRUCTURE_ERROR = 22


def write_manual_record(mode_dir: Path, scored: dict, patch: Path, verifier: Path) -> Path:
    """保存不依赖 Trae 状态文件的机器可读模式结果。"""
    path = mode_dir / "verification" / "MANUAL_RESULT.json"
    payload = {
        "status": "completed",
        "execution_mode": "user_manual",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": scored.get("mode"),
        "reward": scored.get("reward"),
        "verifier": str(verifier),
        "patch": str(patch),
        "result": scored,
    }
    # The final-check reader intentionally consumes the top-level no_skill key.
    if scored.get("mode") == "no-skill":
        payload["no_skill"] = scored
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def ensure_no_skill_source(run_root: Path, baseline: dict, no_skill: dict) -> str:
    """为旧的诊断结果建立可核对的 no-skill 来源记录。"""
    existing = Path(str(no_skill.get("source_result", ""))).expanduser()
    if existing.is_file():
        return str(existing.resolve())
    mode_name = baseline.get("mode_dirs", {}).get("no-skill")
    if not isinstance(mode_name, str) or not mode_name:
        raise ValueError("BASELINE.json 缺少 no-skill 目录映射")
    mode_dir = run_root / mode_name
    verifier_path = mode_dir / "verification" / "VERIFICATION.json"
    if not verifier_path.is_file():
        raise ValueError("旧 no-skill 结果缺少可核对的 VERIFICATION.json，不能升级")
    verifier = read_json(verifier_path)
    if int(verifier.get("reward", 1)) != int(no_skill.get("reward", 1)):
        raise ValueError("旧 no-skill 记录与 VERIFICATION.json 的 reward 不一致")
    path = mode_dir / "verification" / "MANUAL_RESULT.json"
    path.write_text(
        json.dumps(
            {
                "status": "completed",
                "execution_mode": "user_manual",
                "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "no_skill": no_skill,
                "verifier": str(verifier_path),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return str(path)


def grade_manual(args: argparse.Namespace) -> int:
    baseline, task_dir, run_root, mode_dir = load_context(args)
    validate_experiment_inputs(baseline, task_dir, run_root)
    repo = repo_path(baseline, mode_dir, args.mode)
    if not repo.is_dir():
        raise ValueError(f"Trae 工作区不存在：{repo}")
    if args.mode == "with-skill":
        previous_path = run_root / "EXPERIMENT_RESULT.json"
        if not previous_path.is_file():
            raise ValueError("no-skill 尚未判分，不能判 with-skill")
        previous = read_json(previous_path)
        no_skill = previous.get("no_skill")
        if not isinstance(no_skill, dict) or int(no_skill.get("reward", 1)) != 0:
            raise ValueError("no-skill reward 不是 0，不能判 with-skill")
        no_skill = dict(no_skill)
        no_skill["source_result"] = ensure_no_skill_source(run_root, baseline, no_skill)

    output = mode_dir / "trae-output"
    verification = mode_dir / "verification"
    patch_path = output / "model.patch"
    verification_path = verification / "VERIFICATION.json"
    if output.exists() or verification.exists():
        if not args.reuse_existing or not patch_path.is_file() or not verification_path.is_file():
            raise ValueError(
                f"该工作区已有回收或验证结果；如确认它们来自本次手动运行，请使用 --reuse-existing：{mode_dir}"
            )
    else:
        output.mkdir()
        patch_path = output / "model.patch"
        create_patch(repo, str(baseline["baseline_head"]), patch_path)
    verifier = Path(__file__).with_name("verify_agent_patch.py")
    if args.reuse_existing:
        checked = subprocess.CompletedProcess([], 0)
    else:
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
    if not verification_path.is_file():
        payload = infrastructure_result(
            run_root,
            args.mode,
            "verifier 未生成 VERIFICATION.json",
            execution_mode="user_manual",
            exit_code=checked.returncode,
        )
        write_json(run_root / "EXPERIMENT_RESULT.json", payload)
        return INFRASTRUCTURE_ERROR
    scored = read_json(verification_path)
    if scored.get("status") != "completed" or scored.get("reward") not in (0, 1):
        payload = infrastructure_result(
            run_root,
            args.mode,
            "手动 Trae 工作区未得到可用的二元 verifier 结果",
            execution_mode="user_manual",
            verification=scored,
        )
        write_json(run_root / "EXPERIMENT_RESULT.json", payload)
        return INFRASTRUCTURE_ERROR
    scored["mode"] = args.mode
    scored["agent"] = {
        "runner": args.runner,
        "expected_model": baseline.get("expected_model"),
        "workspace": str(repo),
        "prompt_sha256": sha256(mode_dir / "PROMPT.md"),
        "patch_sha256": sha256(patch_path),
        "completion_confirmed": True,
        "completion_evidence": args.evidence or "user-confirmed manual Trae completion",
        "confirmed_complete_at": now(),
    }
    manual_record = write_manual_record(mode_dir, scored, patch_path, verification_path)
    if args.mode == "no-skill":
        scored["source_result"] = str(manual_record)
    else:
        scored["verifier"] = str(verification_path)

    result_path = run_root / "EXPERIMENT_RESULT.json"
    if args.mode == "no-skill":
        if int(scored["reward"]) == 1:
            result = {
                "status": "needs_task_hardening",
                "execution_mode": "user_manual",
                "message": "no-skill 已通过，停止 with-skill；需要提高题目真实推理难度。",
                "no_skill": scored,
                "no_skill_source": str(manual_record),
            }
            exit_code = TASK_TOO_EASY
        else:
            result = {
                "status": "ready_for_with_skill",
                "execution_mode": "user_manual",
                "message": "no-skill reward=0，可以执行 with-skill。",
                "no_skill": scored,
                "no_skill_source": str(manual_record),
            }
            exit_code = READY_FOR_WITH_SKILL
    else:
        previous = read_json(result_path)
        no_skill = previous.get("no_skill")
        if not isinstance(no_skill, dict) or int(no_skill.get("reward", 1)) != 0:
            raise ValueError("no-skill 证据无效，不能写入 with-skill 结果")
        if int(scored["reward"]) == 0:
            result = {
                "status": "needs_skill_revision",
                "execution_mode": "user_manual",
                "message": "no-skill 失败且 with-skill 也失败，需要返修中文专家 skill。",
                "no_skill": no_skill,
                "no_skill_source": previous.get("no_skill_source"),
                "with_skill": scored,
            }
            exit_code = SKILL_NEEDS_REVISION
        else:
            result = {
                "status": "passed",
                "execution_mode": "user_manual",
                "message": "有效对照：no-skill reward=0，with-skill reward=1。",
                "no_skill": no_skill,
                "no_skill_source": previous.get("no_skill_source"),
                "with_skill": scored,
            }
            exit_code = 0
    write_json(result_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("no-skill", "with-skill"), required=True)
    parser.add_argument("--docker", default="docker")
    parser.add_argument(
        "--runner",
        default="Trae CN (user manual)",
        help="实际执行 Agent 的工具名，写入 EXPERIMENT_RESULT.json 的 agent.runner（如 TraeCode、TRAE SOLO CN）",
    )
    parser.add_argument("--evidence", help="可选：用户提供的 Trae 完成记录或日志路径")
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="复用当前工作区已有的 model.patch 和 VERIFICATION.json；仅用于升级已完成的诊断结果",
    )
    args = parser.parse_args()
    try:
        return grade_manual(args)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    return INFRASTRUCTURE_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
