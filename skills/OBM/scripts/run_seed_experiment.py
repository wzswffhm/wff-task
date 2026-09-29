#!/usr/bin/env python3
"""Run no-skill first, then with-skill only after no-skill fails verification."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


TASK_TOO_EASY = 20
SKILL_NEEDS_REVISION = 21
INFRASTRUCTURE_ERROR = 22
TURN_PROFILE_NOT_MET = 23
# 轮次记录仅用于运行分析，不替代独立 verifier 的 reward，也不构成门槛。


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def write_progress(run_root: Path, stage: str, **details: object) -> None:
    write_json_atomic(
        run_root / "EXPERIMENT_PROGRESS.json",
        {"status": "running", "stage": stage, "updated_at": utc_now(), **details},
    )


def write_result(run_root: Path, payload: dict) -> None:
    write_json_atomic(run_root / "EXPERIMENT_RESULT.json", payload)


def finish_progress(run_root: Path, payload: dict) -> None:
    write_json_atomic(
        run_root / "EXPERIMENT_PROGRESS.json",
        {
            "status": "finished",
            "stage": payload.get("status", "unknown"),
            "result_status": payload.get("status"),
            "updated_at": utc_now(),
        },
    )


def baseline_identity(baseline: dict) -> dict:
    return {
        key: baseline.get(key)
        for key in (
            "upstream_sha256",
            "baseline_head",
            "proposal_sha256",
            "verifier_sha256",
            "instruction_sha256",
            "no_skill_prompt_sha256",
            "model",
            "reasoning_effort",
            "max_turns",
            "max_tokens",
        )
    }


def load_accepted_no_skill(
    path: Path, current_baseline: dict, args: argparse.Namespace
) -> dict:
    accepted_path = path.expanduser().resolve()
    if not accepted_path.is_file():
        raise SystemExit(f"找不到已接受的 no-skill 结果：{accepted_path}")
    prior = read_json(accepted_path)
    prior_no_skill = prior.get("no_skill")
    if not isinstance(prior_no_skill, dict):
        raise SystemExit("已接受的结果不包含 no_skill")
    if prior_no_skill.get("status") != "completed" or int(
        prior_no_skill.get("reward", 1)
    ) != 0:
        raise SystemExit("只能复用有有效运行记录且 verifier reward=0 的 no-skill 结果")
    prior_baseline_path = accepted_path.parent / "BASELINE.json"
    if not prior_baseline_path.is_file():
        raise SystemExit(f"上一轮缺少 BASELINE.json：{prior_baseline_path}")
    prior_baseline = read_json(prior_baseline_path)
    if not prior_baseline.get("verifier_sha256") or not current_baseline.get(
        "verifier_sha256"
    ):
        raise SystemExit("BASELINE.json 缺少 verifier 散列，不能安全复用 no-skill")
    if baseline_identity(prior_baseline) != baseline_identity(current_baseline):
        raise SystemExit(
            "题目、题面、verifier、模型或运行参数已变化，不能复用 no-skill；"
            "必须重新执行完整实验"
        )
    agent = prior_no_skill.get("agent")
    if not isinstance(agent, dict):
        raise SystemExit("上一轮 no-skill 缺少 Agent 运行记录，不能安全复用")
    expected_agent = {
        "model_requested": args.model,
        "reasoning_effort": args.reasoning_effort,
        "max_turns": args.max_turns,
        "max_tokens": args.max_tokens,
    }
    actual_agent = {key: agent.get(key) for key in expected_agent}
    if actual_agent != expected_agent:
        raise SystemExit("上一轮 no-skill 的模型或运行参数不同，不能复用")
    return prior_no_skill


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def build_command_image(args: argparse.Namespace) -> Tuple[Optional[str], Optional[dict]]:
    app = args.task_dir / "sources/app"
    if not app.is_dir():
        return None, {
            "status": "infrastructure_error",
            "stage": "command_image",
            "error": "题包缺少 sources/app",
        }
    image = "obm-seed-command:" + tree_hash(app)[:16]
    log = args.run_root / "SEED_COMMAND_IMAGE.log"
    result = subprocess.run(
        [args.docker, "build", "--network=none", "-t", image, str(app)],
        text=True,
        capture_output=True,
    )
    log.write_text(
        "$ "
        + " ".join([args.docker, "build", "--network=none", "-t", image, str(app)])
        + "\n\n"
        + result.stdout
        + result.stderr,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return None, {
            "status": "infrastructure_error",
            "stage": "command_image",
            "exit_code": result.returncode,
            "log": str(log),
        }
    return image, None


def run_mode(args: argparse.Namespace, mode: str) -> dict:
    mode_dir = args.run_root / mode
    agent_output = mode_dir / "seed-output"
    verify_output = mode_dir / "verification"
    runner = Path(__file__).with_name("run_seed_agent.py")
    verifier = Path(__file__).with_name("verify_agent_patch.py")

    write_progress(args.run_root, f"{mode}_agent", mode=mode)
    agent = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--repo",
            str(mode_dir / "repo"),
            "--prompt",
            str(mode_dir / "PROMPT.md"),
            "--output-dir",
            str(agent_output),
            "--env-file",
            str(args.env_file),
            "--model",
            args.model,
            "--reasoning-effort",
            args.reasoning_effort,
            "--max-turns",
            str(args.max_turns),
            "--max-tokens",
            str(args.max_tokens),
            "--docker",
            args.docker,
            "--command-image",
            args.command_image,
        ],
        text=True,
    )
    agent_record_path = agent_output / "API_RUN.json"
    agent_record = read_json(agent_record_path) if agent_record_path.is_file() else None
    allowed_agent_exhaustion = (
        isinstance(agent_record, dict)
        and agent_record.get("status") == "max_turns"
    )
    if agent.returncode != 0 and not allowed_agent_exhaustion:
        return {
            "status": "infrastructure_error",
            "stage": f"{mode}_agent",
            "exit_code": agent.returncode,
        }
    write_progress(
        args.run_root,
        f"{mode}_verification",
        mode=mode,
        turns=int((agent_record or {}).get("turns", 0)),
        agent_status=(agent_record or {}).get("status"),
    )
    verification = subprocess.run(
        [
            sys.executable,
            str(verifier),
            "--task-dir",
            str(args.task_dir),
            "--patch",
            str(agent_output / "model.patch"),
            "--output-dir",
            str(verify_output),
            "--docker",
            args.docker,
        ],
        text=True,
    )
    if verification.returncode != 0:
        detail_path = verify_output / "VERIFICATION.json"
        return read_json(detail_path) if detail_path.is_file() else {
            "status": "infrastructure_error",
            "stage": f"{mode}_verification",
            "exit_code": verification.returncode,
        }
    result = read_json(verify_output / "VERIFICATION.json")
    if int(result.get("apply_failed", 0)) == 1:
        return {
            "status": "infrastructure_error",
            "stage": f"{mode}_patch_apply",
            "error": "model.patch 无法应用，不能把 reward=0 作为有效实验结果",
            "verification": result,
        }
    if result.get("reward") not in (0, 1):
        return {
            "status": "infrastructure_error",
            "stage": f"{mode}_grade",
            "error": "verifier 没有返回有效的二元 reward",
            "verification": result,
        }
    result["agent"] = agent_record or read_json(agent_record_path)
    result["agent"]["completion_confirmed"] = True
    result["agent"]["completion_evidence_source"] = str(agent_record_path)
    result["turn_profile"] = make_turn_profile(args, mode, result["agent"])
    return result


def make_turn_profile(args: argparse.Namespace, mode: str, agent: dict) -> dict:
    turns = int(agent.get("turns", 0))
    if mode == "no-skill":
        preferred_minimum = args.target_no_skill_min_turns
        preference_met = turns >= preferred_minimum
        preference = f"偏好至少 {preferred_minimum} 轮"
        target = {"minimum": preferred_minimum}
    else:
        preferred_turns = args.target_with_skill_turns
        tolerance = args.target_with_skill_tolerance
        lower = max(1, preferred_turns - tolerance)
        upper = preferred_turns + tolerance
        preference_met = lower <= turns <= upper
        preference = f"偏好接近 {preferred_turns} 轮（{lower}-{upper}）"
        target = {
            "preferred": preferred_turns,
            "tolerance": tolerance,
            "range": [lower, upper],
        }
    return {
        "required": False,
        "requirement": "仅作运行分析和题目调优参考，不参与 reward 验收",
        "preference": preference,
        "target": target,
        "turns": turns,
        "completed": agent.get("status") == "completed",
        "preference_met": preference_met,
        "ok": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=Path("model.env"))
    parser.add_argument("--model", default="doubao-seed-evolving")
    parser.add_argument("--reasoning-effort", default="minimal")
    parser.add_argument("--max-turns", type=int, default=120)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--target-no-skill-min-turns", type=int, default=101)
    parser.add_argument("--target-with-skill-turns", type=int, default=70)
    parser.add_argument("--target-with-skill-tolerance", type=int, default=10)
    parser.add_argument(
        "--accepted-no-skill-result",
        type=Path,
        help=(
            "上一轮 EXPERIMENT_RESULT.json；仅在只修改专家 skill 时复用其中 reward=0 的 "
            "no-skill 证据，并从干净基线重跑 with-skill"
        ),
    )
    args = parser.parse_args()
    args.task_dir = args.task_dir.expanduser().resolve()
    args.run_root = args.run_root.expanduser().resolve()
    args.env_file = args.env_file.expanduser().resolve()

    baseline_path = args.run_root / "BASELINE.json"
    if not baseline_path.is_file():
        raise SystemExit(f"缺少 BASELINE.json：{baseline_path}")
    baseline = read_json(baseline_path)
    if (args.run_root / "EXPERIMENT_RESULT.json").exists():
        raise SystemExit("该实验目录已有结果，拒绝覆盖；请创建新的版本化尝试目录")

    if args.max_turns < args.target_no_skill_min_turns:
        raise SystemExit("max-turns 必须不小于 no-skill 偏好最小轮次")
    if args.target_with_skill_turns < 1 or args.target_with_skill_tolerance < 0:
        raise SystemExit("with-skill 轮次偏好和容差必须为有效非负范围")

    write_progress(args.run_root, "command_image_build")
    command_image, error = build_command_image(args)
    if error:
        write_result(args.run_root, error)
        finish_progress(args.run_root, error)
        return INFRASTRUCTURE_ERROR
    args.command_image = command_image

    if args.accepted_no_skill_result:
        write_progress(args.run_root, "no-skill_reuse_validation")
        no_skill = load_accepted_no_skill(
            args.accepted_no_skill_result, baseline, args
        )
        no_skill["turn_profile"] = make_turn_profile(args, "no-skill", no_skill["agent"])
        no_skill_source = str(args.accepted_no_skill_result.expanduser().resolve())
    else:
        no_skill = run_mode(args, "no-skill")
        no_skill_source = str(args.run_root / "no-skill")
    if no_skill.get("status") != "completed":
        result = {
            "status": "infrastructure_error",
            "message": "no-skill 未正常完成，不能据此判断题目难度",
            "no_skill": no_skill,
            "no_skill_source": no_skill_source,
        }
        write_result(args.run_root, result)
        finish_progress(args.run_root, result)
        return INFRASTRUCTURE_ERROR
    if int(no_skill.get("reward", 0)) == 1:
        result = {
            "status": "needs_task_hardening",
            "message": (
                "no-skill 经 verifier 判定通过。停止 with-skill；必须提升公开行为契约和真实推理难度，"
                "重做 NOP/Oracle，并从同一新基线重新生成两套工作区。"
            ),
            "no_skill": no_skill,
            "no_skill_source": no_skill_source,
            "with_skill": None,
        }
        write_result(args.run_root, result)
        finish_progress(args.run_root, result)
        return TASK_TOO_EASY

    with_skill = run_mode(args, "with-skill")
    if with_skill.get("status") != "completed":
        result = {
            "status": "infrastructure_error",
            "message": "with-skill 未正常完成，不能据此修改专家 skill",
            "no_skill": no_skill,
            "no_skill_source": no_skill_source,
            "with_skill": with_skill,
        }
        write_result(args.run_root, result)
        finish_progress(args.run_root, result)
        return INFRASTRUCTURE_ERROR
    if int(with_skill.get("reward", 0)) != 1:
        result = {
            "status": "needs_skill_revision",
            "message": (
                "no-skill 失败且 with-skill 也失败。只能补强可迁移的专家方法，不能写入隐藏测试、"
                "固定失败输入、私有符号或上一轮断言；修改后从干净基线重新创建 with-skill 工作区。"
            ),
            "no_skill": no_skill,
            "no_skill_source": no_skill_source,
            "with_skill": with_skill,
        }
        write_result(args.run_root, result)
        finish_progress(args.run_root, result)
        return SKILL_NEEDS_REVISION

    result = {
        "status": "passed",
        "execution_mode": "seed_api",
        "message": "有效对照：no-skill reward=0，with-skill reward=1。",
        "no_skill": no_skill,
        "no_skill_source": no_skill_source,
        "with_skill": with_skill,
    }
    write_result(args.run_root, result)
    finish_progress(args.run_root, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
