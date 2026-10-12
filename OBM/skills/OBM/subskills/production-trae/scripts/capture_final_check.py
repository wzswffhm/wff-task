#!/usr/bin/env python3
"""Run final skill/package checks and render their terminal output to PNG."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "缺少 Pillow。请先运行：python3 -m pip install 'Pillow>=10,<13'"
    ) from exc


def run(command: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    text = "$ " + " ".join(command) + "\n" + result.stdout + result.stderr
    return result.returncode, text.rstrip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font(size: int):
    candidates = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def render(text: str, output: Path) -> None:
    lines: list[str] = []
    for raw in text.splitlines() or [""]:
        while len(raw) > 115:
            lines.append(raw[:115])
            raw = raw[115:]
        lines.append(raw)
    face = font(18)
    line_height = 27
    width = 1500
    height = max(320, 90 + line_height * len(lines))
    if height > 60_000:
        raise ValueError("检查输出过长，无法安全生成单张 PNG；请先处理异常输出")
    image = Image.new("RGB", (width, height), "#101418")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, 58), fill="#20262d")
    draw.ellipse((22, 20, 38, 36), fill="#ff5f57")
    draw.ellipse((48, 20, 64, 36), fill="#febc2e")
    draw.ellipse((74, 20, 90, 36), fill="#28c840")
    draw.text((112, 17), "OBM final skill check", font=face, fill="#d8dee9")
    y = 72
    for line in lines:
        color = "#ff7b72" if "[FAIL]" in line or "Result: FAIL" in line else "#d8dee9"
        if "[PASS]" in line or "Result: PASS" in line:
            color = "#7ee787"
        if "[WARN]" in line:
            color = "#f2cc60"
        draw.text((22, y), line, font=face, fill=color)
        y += line_height
    image.save(output)


def manual_evidence_ok(experiment: dict, label: str) -> tuple[bool, str]:
    """Validate explicitly recorded user-manual verifier evidence.

    Manual Trae runs do not have a Codex-owned window or listener.  Accept
    them only when the result says so explicitly and points at the independent
    verifier (with-skill) or the previously verified no-skill result.
    """
    if experiment.get("execution_mode") != "user_manual":
        return False, "execution_mode is not user_manual"
    section = experiment.get(label, {})
    if not isinstance(section, dict):
        return False, f"missing {label} section"
    if label == "with_skill":
        path = Path(str(section.get("verifier", ""))).expanduser()
        try:
            verifier = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False, "with-skill verifier record is unreadable"
        ok = (
            verifier.get("status") == "completed"
            and int(verifier.get("container_exit_code", 1)) == 0
            and int(verifier.get("reward", 0)) == 1
            and int(section.get("reward", 0)) == 1
        )
        return ok, f"with-skill verifier={path}"
    path = Path(str(section.get("source_result", ""))).expanduser()
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
        source_section = source.get("no_skill", {})
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "no-skill source result is unreadable"
    ok = int(source_section.get("reward", 1)) == 0 and int(section.get("reward", 1)) == 0
    return ok, f"no-skill source={path}"


def turn_profile_ok(experiment: dict, label: str) -> tuple[bool, str]:
    """Read optional turn information without making it an acceptance gate."""
    section = experiment.get(label, {})
    if not isinstance(section, dict):
        return True, f"{label} turn profile not recorded (optional)"
    profile = section.get("turn_profile", {})
    if not isinstance(profile, dict) or not profile:
        return True, f"{label} turn profile not recorded (optional)"
    agent = section.get("agent", {})
    if not isinstance(agent, dict):
        agent = {}
    raw_turns = profile.get("turns", agent.get("turns"))
    if raw_turns is None:
        return True, f"{label} turn profile not recorded (optional)"
    try:
        turns = int(raw_turns)
    except (TypeError, ValueError):
        return False, f"{label} turn count is missing"
    return True, f"{label} turns={turns}, completed={profile.get('completed')} (informational)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--experiment-result", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--benchmark", default="deepSWE")
    args = parser.parse_args()

    task = args.task_dir.expanduser().resolve()
    experiment_path = args.experiment_result.expanduser().resolve()
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    skill_dir = Path(__file__).resolve().parents[1]
    project_root = Path.cwd().resolve()
    commands = [
        [
            sys.executable,
            str(skill_dir / "scripts/check_skill_language.py"),
            str(task / "sources/skill/SKILL.md"),
        ],
        [
            sys.executable,
            str(skill_dir / "proposal_validator/validate_proposals.py"),
            str(task),
        ],
        [
            sys.executable,
            str(skill_dir / "scripts/check_package.py"),
            str(task),
            "--benchmark",
            args.benchmark,
        ],
    ]
    rows = [run(command, project_root) for command in commands]
    try:
        experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
        automatic_evidence = (
            experiment.get("status") == "passed"
            and experiment.get("execution_mode") == "seed_api"
            and int(experiment.get("no_skill", {}).get("reward", 1)) == 0
            and int(experiment.get("with_skill", {}).get("reward", 0)) == 1
            and experiment.get("no_skill", {})
            .get("agent", {})
            .get("completion_confirmed")
            is True
            and experiment.get("with_skill", {})
            .get("agent", {})
            .get("completion_confirmed")
            is True
        )
        manual_no_skill_ok, manual_no_skill_note = manual_evidence_ok(experiment, "no_skill")
        manual_with_skill_ok, manual_with_skill_note = manual_evidence_ok(experiment, "with_skill")
        experiment_ok = automatic_evidence or (
            experiment.get("status") == "passed"
            and manual_no_skill_ok
            and manual_with_skill_ok
        )
        evidence_mode = "automatic" if automatic_evidence else (
            f"manual ({manual_no_skill_note}; {manual_with_skill_note})"
        )
        experiment_text = (
            f"$ verify experiment result {experiment_path}\n"
            f"status={experiment.get('status')}\n"
            f"no-skill reward={experiment.get('no_skill', {}).get('reward')}\n"
            f"with-skill reward={experiment.get('with_skill', {}).get('reward')}\n"
            f"execution mode={experiment.get('execution_mode')}\n"
            f"turn profile=informational only\n"
            f"evidence mode={evidence_mode}\n"
            f"Result: {'PASS' if experiment_ok else 'FAIL'}"
        )
        rows.append((0 if experiment_ok else 1, experiment_text))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        rows.append(
            (
                1,
                f"$ verify experiment result {experiment_path}\n"
                f"无法读取有效实验结果：{exc}\nResult: FAIL",
            )
        )
    ok = all(code == 0 for code, _ in rows)
    header = (
        f"时间：{datetime.now().astimezone().isoformat(timespec='seconds')}\n"
        f"题包：{task}\n\n"
    )
    body = header + "\n\n".join(text for _, text in rows)
    body += "\n\nFINAL RESULT: " + ("PASS" if ok else "FAIL")
    text_path = output / "FINAL_CHECK.txt"
    image_path = output / "FINAL_CHECK.png"
    json_path = output / "FINAL_CHECK.json"
    text_path.write_text(body + "\n", encoding="utf-8")
    render(body, image_path)
    json_path.write_text(
        json.dumps(
            {
                "ok": ok,
                "task_dir": str(task),
                "experiment_result": str(experiment_path),
                "text": str(text_path),
                "screenshot": str(image_path),
                "text_sha256": sha256(text_path),
                "screenshot_sha256": sha256(image_path),
                "experiment_sha256": sha256(experiment_path)
                if experiment_path.is_file()
                else None,
                "exit_codes": [code for code, _ in rows],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json_path.read_text(encoding="utf-8"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
