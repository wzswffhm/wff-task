#!/usr/bin/env python3
"""Prepare matched, mode-labelled repositories for Trae runs."""

from __future__ import annotations

import atexit
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from check_skill_language import analyze_skill_language


FIXED_DATE = "2000-01-01T00:00:00+00:00"
TASK_ID_RE = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2}-(\d+))(?!\d)")
# Compatibility format for an already-issued legacy package ID such as
# ``09-21-1-0``. New production should continue using TASK_ID_RE.
LEGACY_TASK_ID_RE = re.compile(r"(?<!\d)(\d{2}-\d{2}-\d+-\d+)(?!\d)")


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
            raise ValueError("upstream 归档为空")
        top_levels: set[str] = set()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"归档包含不安全路径：{member.name}")
            if path.parts:
                top_levels.add(path.parts[0])
            if member.issym() or member.islnk():
                link = PurePosixPath(member.linkname)
                if link.is_absolute() or ".." in link.parts:
                    raise ValueError(f"归档包含不安全链接：{member.name}")
        if len(top_levels) != 1:
            raise ValueError("upstream 归档必须只有一个顶层目录")
        with tempfile.TemporaryDirectory(prefix="obm-trae-source-") as temp:
            extracted = Path(temp)
            try:
                bundle.extractall(extracted, filter="data")
            except TypeError:  # Python 3.11 及更早版本没有 filter 参数
                bundle.extractall(extracted)
            source = extracted / next(iter(top_levels))
            if not source.is_dir():
                raise ValueError("upstream 归档的顶层条目不是目录")
            shutil.copytree(source, destination)


def init_repo(repo: Path) -> str:
    run("git", "init", "-q", cwd=repo)
    run("git", "add", "-A", cwd=repo)
    env = os.environ.copy()
    env.update({"GIT_AUTHOR_DATE": FIXED_DATE, "GIT_COMMITTER_DATE": FIXED_DATE})
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


def extract_task_id(task_dir: Path, proposal: dict) -> tuple[str, int, bool]:
    candidates = [task_dir.name, json.dumps(proposal, ensure_ascii=False)]
    for candidate in candidates:
        match = TASK_ID_RE.search(candidate)
        if match:
            return match.group(1), int(match.group(2)), False
        legacy = LEGACY_TASK_ID_RE.search(candidate)
        if legacy:
            return legacy.group(1), int(legacy.group(1).rsplit("-", 1)[1]), True
    raise ValueError("无法从题包名称或 proposal.json 中识别 YYYY-MM-DD-N 或兼容编号")


def task_instruction(proposal: dict, legacy_instruction: Path | None = None) -> str:
    body = proposal.get("proposal", {})
    parts = [
        "任务概述：\n"
        + "\n".join(
            [
                str(body.get("A_modification_idea", "")).strip(),
                str(body.get("B_modification_details", "")).strip(),
            ]
        ).strip(),
        str(body.get("C_agent_task", "")).strip(),
        "任务难点：\n"
        + "\n".join(f"- {item}" for item in body.get("D_task_difficulties", [])),
    ]
    # Older packages may keep the detailed public contract in
    # sources/app/instruction.md. Include it for Trae prompt generation so a
    # repaired legacy package does not lose its API contract when rerun.
    if legacy_instruction is not None and legacy_instruction.is_file():
        detail = legacy_instruction.read_text(encoding="utf-8").strip()
        if detail:
            parts.append("详细公开契约：\n" + detail)
    return "\n\n".join(part for part in parts if part.strip()).strip()


def skill_guidance(skill: str) -> str:
    match = re.match(r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", skill, re.DOTALL)
    guidance = skill[match.end() :] if match else skill
    guidance = guidance.strip()
    if not guidance:
        raise ValueError("专家 SKILL.md 不含可用的解题思路正文")
    return guidance


def write_prompt(path: Path, instruction: str, guidance: str | None = None) -> None:
    sections = [
        "请直接在当前打开的仓库中完成下面的软件工程任务。先阅读相关实现和现有测试，实际修改代码并运行合适的测试，不要只给出建议。不要访问网络，也不要通过修改、删除或跳过测试规避失败。",
        "\n## 题目\n",
        instruction,
    ]
    if guidance is not None:
        sections.extend(
            [
                "\n## 专家解题思路\n",
                "下面的经验用于帮助分析问题，不改变上面的任务契约。",
                guidance,
            ]
        )
    sections.append("\n完成后请简要说明修改内容和实际运行的测试结果。\n")
    path.write_text("\n".join(sections), encoding="utf-8")


def write_record(path: Path, mode: str, head: str, expected_model: str) -> None:
    path.write_text(
        f"""# Trae 运行记录

- 模式：{mode}
- 基线 HEAD：`{head}`
- 预期模型：{expected_model}
- 开始时间：
- 结束时间：
- 原始运行日志路径：
- 运行日志 SHA-256：
- 结束原因：
- 轮次预算：
- Seed 实际轮次：
- 轮次信息：可选，仅用于运行分析，不参与验收
- verifier reward：
- 备注：
""",
        encoding="utf-8",
    )


def baseline_identity(value: dict) -> dict:
    identity = {
        key: value.get(key)
        for key in (
            "upstream_sha256",
            "baseline_head",
            "proposal_sha256",
            "verifier_sha256",
            "instruction_sha256",
            "no_skill_prompt_sha256",
            "expected_model",
        )
    }
    return identity


def normalize_legacy_no_skill_evidence(no_skill: dict) -> dict:
    """Upgrade a verified legacy no-skill record to current evidence fields.

    Older runs recorded completion in TRAE_RUN.json and MONITOR_REQUEST.json,
    but copied ``monitor_status=completing`` into EXPERIMENT_RESULT.json before
    the listener was stopped.  Accept that format only when the authoritative
    mode records, prompt, patch, reward, and workspace all agree.
    """
    agent = no_skill.get("agent")
    if not isinstance(agent, dict):
        return no_skill
    if agent.get("monitor_status") == "stopped" and agent.get(
        "completion_confirmed"
    ) is True:
        return no_skill

    workspace_text = str(agent.get("workspace", "")).strip()
    if not workspace_text:
        return no_skill
    workspace = Path(workspace_text).expanduser().resolve()
    mode_dir = workspace.parent
    state_path = mode_dir / "TRAE_RUN.json"
    monitor_path = mode_dir / "MONITOR_REQUEST.json"
    patch_path = mode_dir / "trae-output" / "model.patch"
    if not (state_path.is_file() and monitor_path.is_file() and patch_path.is_file()):
        return no_skill

    state = json.loads(state_path.read_text(encoding="utf-8"))
    monitor = json.loads(monitor_path.read_text(encoding="utf-8"))
    state_workspace = Path(str(state.get("repo", ""))).expanduser().resolve()
    prompt_matches = (
        str(state.get("prompt_sha256", ""))
        == str(agent.get("prompt_sha256", ""))
        != ""
    )
    patch_matches = (
        sha256(patch_path) == str(agent.get("patch_sha256", "")) != ""
    )
    completion_time = str(state.get("confirmed_complete_at", "")).strip()
    legacy_evidence_valid = (
        state.get("mode") == "no-skill"
        and state.get("status") == "graded"
        and int(state.get("reward", 1)) == 0
        and state_workspace == workspace
        and state.get("monitoring", {}).get("status") == "stopped"
        and monitor.get("status") == "stopped"
        and bool(completion_time)
        and prompt_matches
        and patch_matches
    )
    if not legacy_evidence_valid:
        return no_skill

    normalized = dict(no_skill)
    normalized_agent = dict(agent)
    normalized_agent.update(
        {
            "monitor_status": "stopped",
            "completion_confirmed": True,
            "completion_confirmed_at": completion_time,
            "completion_evidence_source": str(state_path),
        }
    )
    normalized["agent"] = normalized_agent
    return normalized


def load_accepted_no_skill(path: Path, baseline: dict) -> tuple[dict, str, str]:
    accepted_path = path.expanduser().resolve()
    prior = json.loads(accepted_path.read_text(encoding="utf-8"))
    if prior.get("status") != "needs_skill_revision":
        raise ValueError("只能在上一轮 with-skill 正常完成但 reward=0 后复用 no-skill")
    no_skill = prior.get("no_skill")
    if not isinstance(no_skill, dict):
        raise ValueError("复用结果缺少 no_skill")
    no_skill = normalize_legacy_no_skill_evidence(no_skill)
    if no_skill.get("status") != "completed" or int(no_skill.get("reward", 1)) != 0:
        raise ValueError("只能复用有有效运行记录且 verifier reward=0 的 no-skill 结果")
    with_skill = prior.get("with_skill")
    if not isinstance(with_skill, dict) or not (
        with_skill.get("status") == "completed"
        and int(with_skill.get("reward", 1)) == 0
    ):
        raise ValueError("上一轮不是有效的 with-skill reward=0，不能进入 skill 返修重跑")
    prior_with_skill_window_id = ""
    prior_baseline_path = accepted_path.parent / "BASELINE.json"
    prior_baseline = json.loads(prior_baseline_path.read_text(encoding="utf-8"))
    if baseline_identity(prior_baseline) != baseline_identity(baseline):
        raise ValueError("题面、upstream、verifier、no-skill 提示词或模型已变化，不能复用 no-skill")
    if prior_baseline.get("skill_sha256") == baseline.get("skill_sha256"):
        raise ValueError("with-skill 失败后必须先修改中文专家 SKILL.md，不能原样重跑")
    if prior_baseline.get("with_skill_prompt_sha256") == baseline.get(
        "with_skill_prompt_sha256"
    ):
        raise ValueError("返修后的 with-skill 提示词没有变化，拒绝创建新一轮运行")
    prior_match = re.fullmatch(r"trae-runs-v(\d+)", accepted_path.parent.name)
    current_match = re.fullmatch(r"trae-runs-v(\d+)", baseline.get("run_root_name", ""))
    if not prior_match or not current_match:
        raise ValueError("skill 返修目录必须使用 trae-runs-vN 命名")
    prior_version = int(prior_match.group(1))
    current_version = int(current_match.group(1))
    if current_version != prior_version + 1:
        raise ValueError(
            "skill 返修必须使用紧接上一轮的新版本目录："
            f"上一轮 v{prior_version}，本轮应为 v{prior_version + 1}"
        )
    return no_skill, str(accepted_path), prior_with_skill_window_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--expected-model", default="Doubao-Seed-Evolving")
    parser.add_argument(
        "--accepted-no-skill-result",
        type=Path,
        help="只修改专家 skill 时复用上一轮正常失败的 no-skill 证据",
    )
    args = parser.parse_args()

    task_dir = args.task_dir.expanduser().resolve()
    run_root = args.run_root.expanduser().resolve()
    archive = task_dir / "sources/app/upstream.tar.gz"
    skill_path = task_dir / "sources/skill/SKILL.md"
    proposal_path = task_dir / "proposal.json"
    verifier_dir = task_dir / "sources/verifier"
    for required in (archive, skill_path, proposal_path):
        if not required.is_file():
            raise SystemExit(f"缺少文件：{required}")
    if not verifier_dir.is_dir():
        raise SystemExit(f"缺少目录：{verifier_dir}")
    if run_root.exists():
        raise SystemExit(f"运行目录已存在，拒绝覆盖：{run_root}")

    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    task_id, sequence, legacy_id = extract_task_id(task_dir, proposal)
    instruction = task_instruction(proposal, task_dir / "sources/app/instruction.md")
    if not instruction:
        raise SystemExit("proposal.json 不含可用的 Agent 任务契约")
    skill = skill_path.read_text(encoding="utf-8")
    language = analyze_skill_language(skill)
    if language["issues"]:
        raise SystemExit("专家 SKILL.md 未通过中文检查：" + "; ".join(language["issues"]))
    try:
        guidance = skill_guidance(skill)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    directory_prefix = task_id if legacy_id else str(sequence)
    mode_dirs = {
        "no-skill": f"{directory_prefix}-no-skill",
        "with-skill": f"{directory_prefix}-with-repo",
    }
    repo_dir_names = {
        "no-skill": f"{directory_prefix}-no-repo",
        "with-skill": f"{directory_prefix}-with-repo",
    }
    run_root.parent.mkdir(parents=True, exist_ok=True)
    build_root = Path(
        tempfile.mkdtemp(prefix=f".{run_root.name}-building-", dir=run_root.parent)
    )
    atexit.register(shutil.rmtree, build_root, ignore_errors=True)
    heads: dict[str, str] = {}
    for mode in ("no-skill", "with-skill"):
        mode_dir = build_root / mode_dirs[mode]
        repo = mode_dir / repo_dir_names[mode]
        mode_dir.mkdir()
        safe_extract(archive, repo)
        if (repo / ".trae/skills").exists():
            raise SystemExit("upstream 已包含 .trae/skills，可能影响 no-skill/with-skill 对照")
        heads[mode] = init_repo(repo)
        write_prompt(
            mode_dir / "PROMPT.md",
            instruction,
            guidance if mode == "with-skill" else None,
        )
        write_record(mode_dir / "RUN_RECORD.md", mode, heads[mode], args.expected_model)
    if heads["no-skill"] != heads["with-skill"]:
        raise SystemExit("no-skill 与 with-skill 的基线 HEAD 不一致")

    no_skill_prompt = build_root / mode_dirs["no-skill"] / "PROMPT.md"
    with_skill_prompt = build_root / mode_dirs["with-skill"] / "PROMPT.md"
    if no_skill_prompt.read_bytes() == with_skill_prompt.read_bytes():
        raise SystemExit("with-skill 提示词必须额外包含专家解题思路")
    for mode in ("no-skill", "with-skill"):
        if (
            build_root / mode_dirs[mode] / repo_dir_names[mode] / ".trae/skills"
        ).exists():
            raise SystemExit("两侧仓库都不得安装 Trae 项目级 skill")

    baseline = {
        "task_id": task_id,
        "sequence_number": sequence,
        "legacy_id_format": legacy_id,
        "mode_dirs": mode_dirs,
        "repo_dir_names": repo_dir_names,
        "upstream_sha256": sha256(archive),
        "baseline_head": heads["no-skill"],
        "proposal_sha256": sha256(proposal_path),
        "skill_sha256": sha256(skill_path),
        "verifier_sha256": tree_sha256(verifier_dir),
        "instruction_sha256": hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
        "no_skill_prompt_sha256": sha256(no_skill_prompt),
        "with_skill_prompt_sha256": sha256(with_skill_prompt),
        "prompts_identical": False,
        "task_contract_identical": True,
        "with_skill_delivery": "prompt-context",
        "with_skill_path": None,
        "with_skill_guidance_sha256": hashlib.sha256(
            guidance.encode("utf-8")
        ).hexdigest(),
        "expected_model": args.expected_model,
        "formal_package_includes_trae_runs": False,
        "run_root_name": run_root.name,
    }
    accepted_no_skill: dict | None = None
    accepted_source: str | None = None
    if args.accepted_no_skill_result:
        accepted_no_skill, accepted_source, prior_window_id = load_accepted_no_skill(
            args.accepted_no_skill_result, baseline
        )
        baseline["accepted_no_skill_result"] = accepted_source
        baseline["prior_with_skill_window_binding_id"] = prior_window_id
    (build_root / "BASELINE.json").write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if accepted_no_skill is not None:
        result = {
            "status": "ready_for_with_skill",
            "message": "中文专家 skill 已修改，并复用上一轮有效 no-skill 失败证据；可以运行新的 with-skill。",
            "no_skill": accepted_no_skill,
            "no_skill_source": accepted_source,
        }
        (build_root / "EXPERIMENT_RESULT.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    os.replace(build_root, run_root)
    print(json.dumps(baseline, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
