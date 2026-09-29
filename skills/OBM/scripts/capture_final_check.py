#!/usr/bin/env python3
"""Run final checks and render the verified Seed evidence as a dashboard PNG."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# digest-pinned python image used for authoritative package checks on Windows
# hosts (Windows filesystems cannot represent POSIX executable bits).
CHECK_IMAGE = "python@sha256:4d1caded1f729ae443eb803f26ffde7b61e696aeaef62f099abb6dd6b14257c7"


def check_package_command(skill_dir: Path, task: Path, benchmark: str) -> List[str]:
    if sys.platform != "win32":
        return [
            sys.executable,
            str(skill_dir / "scripts/check_package.py"),
            str(task),
            "--benchmark",
            benchmark,
        ]
    # Windows 文件系统不携带 POSIX 可执行位（st_mode 恒 0o666），check_package.py
    # 的 executable 子检查在宿主机上必然误报 FAIL。把权威检查放进 Linux 容器执行，
    # 与官方验收环境保持一致（容器内挂载文件的 mode 为 0755）。
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{task.as_posix()}:/task",
        "-v",
        f"{skill_dir.as_posix()}:/skill:ro",
        os.environ.get("OBM_CHECK_IMAGE", CHECK_IMAGE),
        "python3",
        "/skill/scripts/check_package.py",
        "/task",
        "--benchmark",
        benchmark,
    ]

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "缺少 Pillow。请先运行：python3 -m pip install 'Pillow>=10,<13'"
    ) from exc


def run(command: List[str], cwd: Path) -> Tuple[int, str]:
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
        # Windows: CJK-capable system fonts (PIL's load_default cannot
        # render Chinese and would produce tofu boxes everywhere).
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def fit_text(draw: ImageDraw.ImageDraw, value: str, face: Any, max_width: int) -> str:
    if draw.textlength(value, font=face) <= max_width:
        return value
    suffix = "…"
    shortened = value
    while shortened and draw.textlength(shortened + suffix, font=face) > max_width:
        shortened = shortened[:-1]
    return shortened + suffix


def wrap_text(draw: ImageDraw.ImageDraw, value: str, face: Any, max_width: int, max_lines: int = 4) -> List[str]:
    lines: List[str] = []
    current = ""
    for word in value.split(" "):
        candidate = (current + " " + word).strip()
        if draw.textlength(candidate, font=face) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        kept = lines[:max_lines]
        kept[-1] = fit_text(draw, kept[-1] + "…", face, max_width)
        return kept
    return lines


def render(summary: Dict[str, Any], output: Path) -> None:
    """Render the compact final-check dashboard without manual-review reminders."""
    width = 1440
    image = Image.new("RGB", (width, 1727), "#ffffff")
    draw = ImageDraw.Draw(image)
    face = font(25)
    title_face = font(34)
    section_face = font(28)
    small_face = font(21)
    metric_face = font(38)
    ink, muted, line = "#182536", "#63758b", "#cbd6e2"
    green, green_bg = "#137548", "#e7f5ec"
    red, red_bg = "#b54439", "#fdece9"
    amber, amber_bg, amber_line = "#9a6700", "#fff8e1", "#e3b341"
    margin, right = 32, width - 32
    text_width = right - margin - 220

    draw.rounded_rectangle(
        (1, 1, width - 2, image.height - 2),
        radius=28,
        outline="#d4dce5",
        width=2,
        fill="#ffffff",
    )
    draw.rounded_rectangle((2, 2, width - 3, 70), radius=26, fill="#f7f9fb")
    draw.rectangle((2, 44, width - 3, 70), fill="#f7f9fb")
    draw.line((2, 70, width - 3, 70), fill=line, width=2)
    for x, color in ((34, "#ff5f57"), (78, "#febc2e"), (122, "#28c840")):
        draw.ellipse((x - 13, 22, x + 13, 48), fill=color)
    draw.text((170, 18), "OBM 最终质检  ·  deepSWE", font=face, fill=ink)

    draw.text(
        (margin, 97),
        fit_text(draw, summary["task_name"], title_face, right - margin),
        font=title_face,
        fill=ink,
    )
    draw.text(
        (margin, 146),
        "检测日期  {date}     |     题号  {task_id}     |     运行版本  {run_version}".format(
            **summary
        ),
        font=small_face,
        fill=muted,
    )

    passed = summary["ok"]
    warnings: List[str] = summary.get("warnings") or []
    banner_color, banner_bg = (green, green_bg) if passed else (red, red_bg)
    draw.rounded_rectangle(
        (margin, 201, right, 329),
        radius=10,
        outline=banner_color,
        width=2,
        fill=banner_bg,
    )
    draw.rounded_rectangle((54, 231, 181, 270), radius=4, fill=banner_color)
    draw.text((72, 235), "ACCEPT" if passed else "FAIL", font=face, fill="#ffffff")
    draw.text(
        (220, 221),
        "通过最终质检" if passed else "最终质检未通过",
        font=section_face,
        fill=banner_color,
    )
    banner_sub = f"{summary['passed_checks']}/4 项检查通过"
    if warnings:
        banner_sub += f"；{len(warnings)} 项人工复核提醒"
    draw.text((220, 268), banner_sub + "。", font=small_face, fill=ink)

    metrics = [
        (str(summary["error_count"]), "校验错误"),
        (str(summary["blocking_count"]), "阻断项"),
        (f"{summary['passed_checks']}/4", "质检项目通过"),
        (str(len(warnings)), "人工复核提醒"),
    ]
    gap = 18
    card_count = len(metrics)
    card_width = (right - margin - gap * (card_count - 1)) // card_count
    for index, (value, label) in enumerate(metrics):
        x0 = margin + index * (card_width + gap)
        draw.rounded_rectangle(
            (x0, 365, x0 + card_width, 481),
            radius=8,
            outline=line,
            width=2,
            fill="#ffffff",
        )
        draw.text((x0 + 20, 381), value, font=metric_face, fill=ink)
        draw.text((x0 + 20, 437), label, font=small_face, fill=muted)

    draw.text((margin, 521), "主要检测结果", font=section_face, fill=ink)
    draw.line((margin, 566, right, 566), fill=line, width=2)
    seed_detail = "no-skill reward=0；with-skill reward=1"
    checks = [
        ("专家 SKILL.md", "专家 SKILL.md pass"),
        ("提案格式", "官方提案校验通过"),
        ("Source 题包", "expert_experience_skill pass；包结构检查通过"),
        ("Seed 对照", seed_detail),
    ]
    for index, (label, detail) in enumerate(checks):
        y0 = 578 + index * 78
        if index % 2 == 0:
            draw.rectangle((margin, y0, right, y0 + 78), fill="#f2f6f9")
        draw.text((margin + 14, y0 + 22), label, font=face, fill=ink)
        status = "PASS" if summary["check_codes"][index] == 0 else "FAIL"
        draw.text(
            (319, y0 + 22), status, font=face, fill=green if status == "PASS" else red
        )
        draw.text((450, y0 + 23), detail, font=small_face, fill=muted)

    cursor = 890
    if warnings:
        cursor += 45
        draw.text((margin, cursor), "需要处理", font=section_face, fill=ink)
        cursor += 35
        note_lines: List[str] = []
        for warning in warnings:
            note_lines.extend(wrap_text(draw, warning, small_face, text_width - 130))
        box_height = max(64, 30 + len(note_lines) * 30)
        draw.rounded_rectangle(
            (margin, cursor, right, cursor + box_height),
            radius=8,
            outline=amber_line,
            width=2,
            fill=amber_bg,
        )
        draw.rounded_rectangle(
            (margin + 16, cursor + 14, margin + 96, cursor + 48),
            radius=4,
            outline=amber,
            width=2,
            fill=amber_bg,
        )
        draw.text((margin + 26, cursor + 19), "待复核", font=small_face, fill=amber)
        for line_index, note in enumerate(note_lines):
            draw.text(
                (margin + 120, cursor + 18 + line_index * 30), note, font=small_face, fill=ink
            )
        cursor += box_height

    cursor += 55
    draw.text((margin, cursor), "Seed 对照证据  ·  Doubao-Seed-Evolving", font=section_face, fill=ink)
    cursor += 45
    draw.line((margin, cursor, right, cursor), fill=line, width=2)
    cursor += 27
    panel_gap = 28
    panel_width = (right - margin - panel_gap) // 2
    panels = (
        (
            "no-skill",
            summary["no_skill"],
            summary["no_skill_preference_met"],
            red,
            red_bg,
        ),
        (
            "with-skill",
            summary["with_skill"],
            summary["with_skill_preference_met"],
            green,
            green_bg,
        ),
    )
    for index, (label, data, preference_met, color, bg) in enumerate(panels):
        x0 = margin + index * (panel_width + panel_gap)
        draw.rounded_rectangle(
            (x0, cursor, x0 + panel_width, cursor + 200),
            radius=9,
            outline=color,
            width=2,
            fill=bg,
        )
        reward = data.get("reward", "?")
        draw.text(
            (x0 + 20, cursor + 18), f"{label}  ·  reward={reward}", font=section_face, fill=color
        )
        # F2P/P2P per-node totals are mandatory evidence detail; the values
        # are parsed from the verifier run log (load_verifier_stats).
        detail = (
            f"F2P  {data.get('f2p_passed', '?')}/{data.get('f2p_total', '?')}     "
            f"P2P  {data.get('p2p_passed', '?')}/{data.get('p2p_total', '?')}"
        )
        draw.text((x0 + 20, cursor + 74), detail, font=face, fill=ink)
        if preference_met:
            turns = (
                summary["no_skill_turns"]
                if label == "no-skill"
                else summary["with_skill_turns"]
            )
            target = (
                summary["no_skill_target"]
                if label == "no-skill"
                else summary["with_skill_target"]
            )
            draw.text(
                (x0 + 20, cursor + 135),
                f"轮次  {turns}  ·  达到偏好范围（{target}）",
                font=small_face,
                fill=color,
            )
    cursor += 200

    cursor += 48
    draw.text((margin, cursor), "证据绑定", font=section_face, fill=ink)
    cursor += 45
    draw.line((margin, cursor, right, cursor), fill=line, width=2)
    cursor += 23
    draw.rounded_rectangle((margin, cursor, right, cursor + 113), radius=8, fill="#182231")
    draw.text((margin + 20, cursor + 16), "Proposal", font=small_face, fill="#a7b7ca")
    draw.text(
        (margin + 164, cursor + 16), summary["proposal_sha256"], font=small_face, fill="#f0f4f8"
    )
    draw.text((margin + 20, cursor + 66), "Result", font=small_face, fill="#a7b7ca")
    draw.text(
        (margin + 164, cursor + 66), summary["result_sha256"], font=small_face, fill="#f0f4f8"
    )
    cursor += 113
    cursor += 29
    draw.text(
        (margin, cursor),
        "质检命令退出码：" + ", ".join(map(str, summary["check_codes"])),
        font=small_face,
        fill=muted,
    )
    image.save(output)


def load_verifier_stats(run_root: Path, side_key: str) -> Dict[str, Any]:
    """Extract F2P/P2P counts from the verifier run log (best effort).

    The grader prints a JSON block with
    {"reward": n, "f2p": {"expected": n, "passed": n, ...}, "p2p": {...}};
    those per-node totals are the authoritative Seed evidence detail.
    """
    side_dir = "no-skill" if side_key == "no_skill" else "with-skill"
    log_path = run_root / side_dir / "verification" / "VERIFIER_RUN.log"
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    start = text.find("{")
    while start != -1:
        try:
            block, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        if isinstance(block, dict) and "f2p" in block and "p2p" in block:
            f2p, p2p = block.get("f2p") or {}, block.get("p2p") or {}
            return {
                "f2p_passed": f2p.get("passed"),
                "f2p_total": f2p.get("expected"),
                "p2p_passed": p2p.get("passed"),
                "p2p_total": p2p.get("expected"),
            }
        start = text.find("{", start + 1)
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--experiment-result", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--benchmark", default="deepSWE")
    args = parser.parse_args()

    task = args.task_dir.expanduser().resolve()
    experiment_path = args.experiment_result.expanduser().resolve()
    turn_stats_path = experiment_path.parent / "TURN_STATS.json"
    output = args.output_dir.expanduser().resolve()
    expected_outputs = [
        output / "FINAL_CHECK.txt",
        output / "FINAL_CHECK.json",
        output / "FINAL_CHECK.png",
    ]
    existing = [str(path) for path in expected_outputs if path.exists()]
    if existing:
        raise ValueError("最终质检输出已存在，拒绝覆盖：\n" + "\n".join(existing))
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
        check_package_command(skill_dir, task, args.benchmark),
    ]
    rows = [run(command, project_root) for command in commands]
    experiment: Dict[str, Any] = {}
    try:
        experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
        experiment_ok = (
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
        experiment_text = (
            f"$ verify experiment result {experiment_path}\n"
            f"status={experiment.get('status')}\n"
            f"no-skill reward={experiment.get('no_skill', {}).get('reward')}\n"
            f"with-skill reward={experiment.get('with_skill', {}).get('reward')}\n"
            f"Result: {'PASS' if experiment_ok else 'FAIL'}"
        )
        rows.append((0 if experiment_ok else 1, experiment_text))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        rows.append((1, f"$ verify experiment result {experiment_path}\n{exc}\nResult: FAIL"))

    turn_stats: Dict[str, Any] = {}
    try:
        turn_stats = json.loads(turn_stats_path.read_text(encoding="utf-8"))
        strict = turn_stats.get("strict_acceptance", {})
        turns = turn_stats.get("turns", {})
        preferences = turn_stats.get("turn_preferences", {})
        no_preference = preferences.get("no_skill", {}).get("met")
        with_preference = preferences.get("with_skill", {}).get("met")
        turn_stats_ok = (
            strict.get("passed") is True
            and isinstance(turns.get("no_skill"), int)
            and isinstance(turns.get("with_skill"), int)
        )
        turn_stats_text = (
            f"$ verify turn stats {turn_stats_path}\n"
            f"strict acceptance={strict.get('passed')}\n"
            f"no-skill turns={turns.get('no_skill')} preference_met={no_preference}\n"
            f"with-skill turns={turns.get('with_skill')} preference_met={with_preference}\n"
            f"Result: {'PASS' if turn_stats_ok else 'FAIL'}"
        )
        rows.append((0 if turn_stats_ok else 1, turn_stats_text))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        rows.append((1, f"$ verify turn stats {turn_stats_path}\n{exc}\nResult: FAIL"))

    raw_codes = [code for code, _ in rows]
    check_codes = raw_codes[:3] + [max(raw_codes[3:5])]
    ok = all(code == 0 for code in raw_codes)
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

    task_id_match = re.match(r"^[^_]+_(\d{4}-\d{2}-\d{2}-\d+)(?:-|$)", task.name)
    if not task_id_match:
        raise ValueError(f"无法从题包目录名解析题号：{task.name}")
    turns = turn_stats.get("turns", {})
    preferences = turn_stats.get("turn_preferences", {})
    no_preference = preferences.get("no_skill", {}).get("met") is True
    with_preference = preferences.get("with_skill", {}).get("met") is True
    no_minimum = preferences.get("no_skill", {}).get("preferred_minimum", 101)
    with_range = preferences.get("with_skill", {}).get("range", [60, 80])
    if not isinstance(with_range, list) or len(with_range) != 2:
        with_range = [60, 80]
    summary = {
        "task_name": task.name,
        "task_id": task_id_match.group(1),
        "run_version": experiment_path.parent.name,
        "date": datetime.now().astimezone().date().isoformat(),
        "ok": ok,
        "passed_checks": sum(code == 0 for code in check_codes),
        "warnings": [
            line[len("[WARN] "):] if line.startswith("[WARN] ") else line
            for _, text in rows
            for line in text.splitlines()
            if line.startswith("[WARN]")
        ],
        "error_count": sum(
            line.startswith("[FAIL]") or "Result: FAIL" in line
            for _, text in rows
            for line in text.splitlines()
        ),
        "blocking_count": sum(code != 0 for code in check_codes),
        "check_codes": check_codes,
        "no_skill": {
            **experiment.get("no_skill", {}),
            **load_verifier_stats(experiment_path.parent, "no_skill"),
        },
        "with_skill": {
            **experiment.get("with_skill", {}),
            **load_verifier_stats(experiment_path.parent, "with_skill"),
        },
        "no_skill_turns": int(turns.get("no_skill", 0) or 0),
        "with_skill_turns": int(turns.get("with_skill", 0) or 0),
        "no_skill_preference_met": no_preference,
        "with_skill_preference_met": with_preference,
        "all_turn_preferences_met": no_preference and with_preference,
        "turn_preferences_met_count": int(no_preference) + int(with_preference),
        "no_skill_target": f"≥{no_minimum}",
        "with_skill_target": f"{with_range[0]}–{with_range[1]}",
        "proposal_sha256": sha256(task / "proposal.json"),
        "result_sha256": sha256(experiment_path),
    }
    render(summary, image_path)
    final_check = {
        "ok": ok,
        "task_dir": str(task),
        "experiment_result": str(experiment_path),
        "turn_stats": str(turn_stats_path),
        "text": str(text_path),
        "screenshot": str(image_path),
        "text_sha256": sha256(text_path),
        "screenshot_sha256": sha256(image_path),
        "experiment_sha256": sha256(experiment_path) if experiment_path.is_file() else None,
        "turn_stats_sha256": sha256(turn_stats_path) if turn_stats_path.is_file() else None,
        "exit_codes": raw_codes,
        "dashboard_check_codes": check_codes,
        "turns": {
            "no_skill": summary["no_skill_turns"],
            "with_skill": summary["with_skill_turns"],
        },
        "turn_preferences_met": {
            "no_skill": no_preference,
            "with_skill": with_preference,
        },
    }
    json_path.write_text(
        json.dumps(final_check, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json_path.read_text(encoding="utf-8"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
