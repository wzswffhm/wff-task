#!/usr/bin/env python3
"""Render two evidence PNGs directly from summarize_model_runs.py JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT = 1600, 900
BG = "#f5f7fb"
INK = "#14213d"
MUTED = "#64748b"
CARD = "#ffffff"
GOOD = "#15803d"
BAD = "#b91c1c"
ACCENT = "#2563eb"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(box, radius=22, fill=CARD, outline="#dbe3ef", width=2)


def ellipsis(value: object, limit: int = 38) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def header(draw: ImageDraw.ImageDraw, title: str, summary: dict) -> None:
    draw.text((70, 48), title, font=font(38, True), fill=INK)
    subtitle = f"Task: {summary.get('task_id')}   Version: {', '.join(summary.get('task_versions') or ['unknown'])}"
    draw.text((72, 104), subtitle, font=font(21), fill=MUTED)
    draw.text((72, 137), f"Generated: {summary.get('generated_at')}", font=font(17), fill=MUTED)


def render_controls(summary: dict, output: Path) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "Oracle / No-change Control Evidence", summary)
    controls = summary.get("controls", {})
    passed = bool(controls.get("passed"))
    draw.rounded_rectangle((1260, 55, 1515, 120), radius=18, fill="#dcfce7" if passed else "#fee2e2")
    draw.text((1300, 72), "PASS" if passed else "FAIL", font=font(28, True), fill=GOOD if passed else BAD)

    sections = [("No-change (expected 0)", controls.get("no_change", [])), ("Golden / Oracle (expected 1)", controls.get("golden", []))]
    for index, (label, runs) in enumerate(sections):
        y0 = 205 + index * 310
        card(draw, (65, y0, 1535, y0 + 270))
        draw.text((95, y0 + 28), label, font=font(27, True), fill=INK)
        for row, run in enumerate(runs):
            y = y0 + 88 + row * 52
            verdict = run.get("verdict")
            color = GOOD if verdict in (0, 1) else BAD
            draw.text((105, y), f"Run {row + 1}", font=font(20, True), fill=ACCENT)
            draw.text((245, y), ellipsis(run.get("run_id"), 34), font=font(19), fill=INK)
            draw.text((700, y), f"verdict={verdict}", font=font(19, True), fill=color)
            draw.text((920, y), f"duration={run.get('duration_seconds')}s", font=font(18), fill=MUTED)
            draw.text((1210, y), ellipsis(run.get("test_log_sha256"), 20), font=font(16), fill=MUTED)
    image.save(output)


def render_scores(summary: dict, output: Path) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    header(draw, "Official Model Score Evidence", summary)
    qualified = bool(summary.get("gates", {}).get("qualified"))
    draw.rounded_rectangle((1260, 55, 1515, 120), radius=18, fill="#dcfce7" if qualified else "#fee2e2")
    draw.text((1287, 72), "QUALIFIED" if qualified else "NOT READY", font=font(25, True), fill=GOOD if qualified else BAD)

    card(draw, (65, 200, 1535, 680))
    columns = [95, 300, 510, 775, 1010, 1260]
    headers = ["Model", "Valid / Required", "Scores", "Score sum", "Invalid attempts", "Complete"]
    for x, label in zip(columns, headers):
        draw.text((x, 235), label, font=font(20, True), fill=MUTED)
    for row, model in enumerate(("QWEN", "OPUS", "GLM", "KIMI")):
        info = summary.get("models", {}).get(model, {})
        y = 315 + row * 80
        if row:
            draw.line((90, y - 24, 1510, y - 24), fill="#e5eaf2", width=2)
        draw.text((columns[0], y), model, font=font(25, True), fill=INK)
        draw.text((columns[1], y), f"{info.get('valid_count', 0)} / {info.get('required', 0)}", font=font(22), fill=INK)
        draw.text((columns[2], y), str(info.get("scores", [])), font=font(22), fill=INK)
        draw.text((columns[3], y), str(info.get("score_sum", 0)), font=font(22, True), fill=INK)
        draw.text((columns[4], y), str(len(info.get("invalid_attempts", []))), font=font(22), fill=MUTED)
        complete = bool(info.get("complete"))
        draw.text((columns[5], y), "YES" if complete else "NO", font=font(22, True), fill=GOOD if complete else BAD)

    gates = summary.get("gates", {})
    card(draw, (65, 715, 1535, 835))
    opus = summary.get("models", {}).get("OPUS", {}).get("score_sum", 0)
    qwen = summary.get("models", {}).get("QWEN", {}).get("score_sum", 0)
    draw.text((95, 747), f"Differentiation: Opus {opus} > Qwen {qwen}", font=font(26, True), fill=GOOD if gates.get("opus_sum_greater_than_qwen") else BAD)
    draw.text((95, 790), f"Controls passed: {gates.get('controls_passed')}   Counts complete: {gates.get('model_counts_complete')}   Version consistent: {gates.get('task_version_consistent')}", font=font(19), fill=MUTED)
    image.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8-sig"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    controls = output_dir / "oracle_nop_controls.png"
    scores = output_dir / "score_summary.png"
    render_controls(summary, controls)
    render_scores(summary, scores)
    print(json.dumps({"oracle_nop": str(controls.resolve()), "scores": str(scores.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

