#!/usr/bin/env python3
"""Prepare matched no-skill and with-skill repositories for Seed API runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from check_skill_language import analyze_skill_language
from check_proposal_language import analyze_proposal_language


FIXED_DATE = "2000-01-01T00:00:00+00:00"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def run(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        list(args), cwd=cwd, check=True, text=True, capture_output=True
    )
    return result.stdout.strip()


def safe_extract(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        if not members:
            raise ValueError("upstream archive is empty")

        top_levels = set()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"unsafe archive path: {member.name}")
            if path.parts:
                top_levels.add(path.parts[0])
            if member.issym() or member.islnk():
                link = PurePosixPath(member.linkname)
                if link.is_absolute() or ".." in link.parts:
                    raise ValueError(f"unsafe archive link: {member.name}")

        if len(top_levels) != 1:
            raise ValueError("upstream archive must contain one top-level directory")

        with tempfile.TemporaryDirectory(prefix="obm-agent-source-") as temp:
            extracted = Path(temp)
            bundle.extractall(extracted)
            source = extracted / next(iter(top_levels))
            if not source.is_dir():
                raise ValueError("archive top-level entry is not a directory")
            shutil.copytree(source, destination)


def init_repo(repo: Path) -> str:
    run("git", "init", "-q", cwd=repo)
    run("git", "add", "-A", cwd=repo)
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_DATE": FIXED_DATE,
            "GIT_COMMITTER_DATE": FIXED_DATE,
        }
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=upstream",
            "-c",
            "user.email=upstream@local",
            "commit",
            "-q",
            "-m",
            "OBM upstream baseline",
        ],
        cwd=repo,
        env=env,
        check=True,
    )
    return run("git", "rev-parse", "HEAD", cwd=repo)


def write_prompt(path: Path, instruction: str, skill: str | None) -> None:
    sections = [
        "请直接在当前打开的仓库中完成下面的软件工程任务。先阅读相关实现和现有测试，实际修改代码并运行合适的测试，不要只给出建议。不要访问网络，也不要通过修改、删除或跳过测试规避失败。",
        "\n## 题目\n",
        instruction.strip(),
    ]
    if skill is not None:
        sections.extend(
            [
                "\n## 专家经验\n",
                "下面的经验用于帮助分析问题。它不改变上面的任务契约。",
                skill.strip(),
            ]
        )
    sections.append("\n完成后请简要说明修改内容和实际运行的测试结果。\n")
    path.write_text("\n".join(sections), encoding="utf-8")


def write_record(
    path: Path,
    mode: str,
    head: str,
    no_skill_minimum: int,
    with_skill_preferred: int,
    with_skill_tolerance: int,
) -> None:
    if mode == "no-skill":
        turn_preference = f"偏好至少 {no_skill_minimum} 轮"
    else:
        lower = max(1, with_skill_preferred - with_skill_tolerance)
        upper = with_skill_preferred + with_skill_tolerance
        turn_preference = f"偏好接近 {with_skill_preferred} 轮（{lower}-{upper}）"
    path.write_text(
        f"""# Agent 运行记录

- 模式：{mode}
- 基线 HEAD：`{head}`
- Agent / 模型：
- 开始时间：
- 结束时间：
- 总耗时：
- 总轮次：
- 轮次信息：由监控器统计；{turn_preference}；仅用于运行分析，不参与 reward 验收
- 网络和权限配置：
- 是否正常完成：
- Agent 最终回复：
- 备注：
""",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument(
        "--run-seed",
        action="store_true",
        help="launch the sequential Seed experiment in the background after preparation",
    )
    parser.add_argument(
        "--foreground",
        action="store_true",
        help="debug only: keep the Seed monitor attached instead of returning immediately",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path("model.env"),
        help="KEY=value file containing key and url for the OpenAI-compatible API",
    )
    parser.add_argument(
        "--model",
        default="doubao-seed-evolving",
        help="OpenAI-compatible model ID",
    )
    parser.add_argument(
        "--reasoning-effort",
        default="minimal",
        choices=("minimal", "low", "medium", "high"),
        help="reasoning effort passed to the Seed model",
    )
    parser.add_argument("--max-turns", type=int, default=120)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--target-no-skill-min-turns", type=int, default=101)
    parser.add_argument("--target-with-skill-turns", type=int, default=70)
    parser.add_argument("--target-with-skill-tolerance", type=int, default=10)
    parser.add_argument(
        "--accepted-no-skill-result",
        type=Path,
        help="reuse a prior verified reward=0 no-skill result when only skill changed",
    )
    args = parser.parse_args()

    if args.max_turns < args.target_no_skill_min_turns:
        raise SystemExit("max-turns must be at least target-no-skill-min-turns")
    if args.target_with_skill_turns < 1 or args.target_with_skill_tolerance < 0:
        raise SystemExit("with-skill turn preference and tolerance must be valid")
    if args.poll_seconds < 1 or args.timeout_seconds < 0:
        raise SystemExit("poll-seconds must be positive and timeout-seconds non-negative")
    if args.foreground and not args.run_seed:
        raise SystemExit("--foreground requires --run-seed")

    task_dir = args.task_dir.resolve()
    run_root = args.run_root.resolve()
    archive = task_dir / "sources/app/upstream.tar.gz"
    skill_path = task_dir / "sources/skill/SKILL.md"
    proposal_path = task_dir / "proposal.json"

    for required in (archive, skill_path, proposal_path):
        if not required.is_file():
            raise SystemExit(f"missing required file: {required}")
    if run_root.exists():
        raise SystemExit(f"run root already exists; refusing to overwrite: {run_root}")

    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    proposal_language = analyze_proposal_language(proposal)
    if proposal_language["issues"]:
        preview_issues = proposal_language["issues"][:8]
        details = "; ".join(
            f"{issue['location']}: {issue['message']}"
            for issue in preview_issues
        )
        remaining = len(proposal_language["issues"]) - len(preview_issues)
        if remaining:
            details += f"; 另有 {remaining} 项问题，请运行 check_proposal_language.py 查看"
        raise SystemExit(
            "proposal.json must use natural Chinese prose before Agent runs are "
            f"prepared: {details}"
        )
    body = proposal.get("proposal", {})
    instruction = "\n\n".join(
        [
            "Task overview:\n" + "\n".join(
                [
                    str(body.get("A_modification_idea", "")).strip(),
                    str(body.get("B_modification_details", "")).strip(),
                ]
            ).strip(),
            str(body.get("C_agent_task", "")).strip(),
            "Task difficulties:\n" + "\n".join(
                f"- {item}" for item in body.get("D_task_difficulties", [])
            ),
        ]
    ).strip()
    if not instruction:
        raise SystemExit("proposal.json does not contain an agent task contract")
    skill = skill_path.read_text(encoding="utf-8")
    language = analyze_skill_language(skill)
    if language["issues"]:
        details = "; ".join(language["issues"])
        raise SystemExit(
            "sources/skill/SKILL.md must be written in Chinese before Agent runs "
            f"are prepared: {details}"
        )
    run_root.mkdir(parents=True)

    heads = {}
    for mode in ("no-skill", "with-skill"):
        mode_dir = run_root / mode
        repo = mode_dir / "repo"
        mode_dir.mkdir()
        safe_extract(archive, repo)
        heads[mode] = init_repo(repo)
        write_prompt(
            mode_dir / "PROMPT.md",
            instruction,
            skill if mode == "with-skill" else None,
        )
        write_record(
            mode_dir / "RUN_RECORD.md",
            mode,
            heads[mode],
            args.target_no_skill_min_turns,
            args.target_with_skill_turns,
            args.target_with_skill_tolerance,
        )

    if heads["no-skill"] != heads["with-skill"]:
        raise SystemExit("baseline HEAD mismatch")

    for mode in ("no-skill", "with-skill"):
        status = run("git", "status", "--porcelain", cwd=run_root / mode / "repo")
        if status:
            raise SystemExit(f"{mode} repository is not clean")

    baseline = {
        "upstream_sha256": sha256(archive),
        "baseline_head": heads["no-skill"],
        "proposal_sha256": sha256(proposal_path),
        "skill_sha256": sha256(skill_path),
        "verifier_sha256": tree_sha256(task_dir / "sources/verifier"),
        "instruction_sha256": hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
        "no_skill_prompt_sha256": sha256(run_root / "no-skill/PROMPT.md"),
        "with_skill_prompt_sha256": sha256(run_root / "with-skill/PROMPT.md"),
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "max_turns": args.max_turns,
        "max_tokens": args.max_tokens,
        "turn_preferences": {
            "required": False,
            "no_skill_minimum": args.target_no_skill_min_turns,
            "with_skill_preferred": args.target_with_skill_turns,
            "with_skill_tolerance": args.target_with_skill_tolerance,
        },
        "no_skill_repo": "no-skill/repo",
        "with_skill_repo": "with-skill/repo",
        "formal_package_includes_agent_runs": False,
    }
    (run_root / "BASELINE.json").write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(baseline, ensure_ascii=False, indent=2), flush=True)

    if args.run_seed:
        runner = Path(__file__).with_name(
            "monitor_seed_experiment.py" if args.foreground else "launch_seed_background.py"
        )
        command = [
            sys.executable,
            str(runner),
            "--task-dir",
            str(task_dir),
            "--run-root",
            str(run_root),
            "--env-file",
            str(args.env_file.expanduser().resolve()),
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
            "--poll-seconds",
            str(args.poll_seconds),
            "--timeout-seconds",
            str(args.timeout_seconds),
            "--target-no-skill-min-turns",
            str(args.target_no_skill_min_turns),
            "--target-with-skill-turns",
            str(args.target_with_skill_turns),
            "--target-with-skill-tolerance",
            str(args.target_with_skill_tolerance),
            "--finalize-on-pass",
        ]
        if args.accepted_no_skill_result:
            command.extend(
                [
                    "--accepted-no-skill-result",
                    str(args.accepted_no_skill_result.expanduser().resolve()),
                ]
            )
        result = subprocess.run(command, text=True)
        if result.returncode != 0:
            print(
                "Agent materials were prepared, but the Seed experiment could not be "
                "started or did not pass in foreground mode. Inspect the run directory "
                "before creating a new clean attempt directory.",
                file=sys.stderr,
            )
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
