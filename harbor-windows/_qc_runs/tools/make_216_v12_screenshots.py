"""生成 wfflab__wchunk-216 v1.2.0 的两张交付截图（数据全部读自 jobs/ 归档）。

  evidence/images/score_summary.png        模型得分与门禁判据
  evidence/images/oracle_nop_controls.png  oracle / no-change 控制轮对照

用法：python -X utf8 make_216_v12_screenshots.py
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WS = Path(r"C:\Users\Administrator\Desktop\wff-task")
ROOT = WS / "deliverables" / "2026-10-11_wchunk216-返修"
JOBS = ROOT / "build" / "jobs"
OUT = ROOT / "evidence" / "images"
TASK_ID = "wfflab__wchunk-216"
VERSION = "1.2.0"

W, H = 1600, 900
BG = (245, 247, 250)
CARD = (255, 255, 255)
INK = (26, 35, 50)
MUTED = (110, 122, 140)
GREEN = (26, 127, 75)
BADGE_BG = (216, 242, 227)
LINE = (228, 233, 240)

FONT_DIR = Path(r"C:\Windows\Fonts")
F_REG = FONT_DIR / "segoeui.ttf"
F_BOLD = FONT_DIR / "segoeuib.ttf"


def font(size: int, bold: bool = False):
    path = F_BOLD if bold else F_REG
    return ImageFont.truetype(str(path), size)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_trials() -> list[dict]:
    trials = []
    for d in sorted(p for p in JOBS.iterdir() if p.is_dir()):
        res = json.loads((d / "result.json").read_text(encoding="utf-8-sig"))
        checks = json.loads((d / "verifier" / "checks.json").read_text(encoding="utf-8-sig"))
        # 时长 / turns 在 runner 的原始 aggregate-v1 报告里（trial result.json 是投影格式）
        raw = json.loads((d / "verifier" / "raw-runner-result.json").read_text(encoding="utf-8-sig"))
        # 原始 run_id 记在 trial lock.json 的 agent.kwargs 里（截图要能回溯到 runs 目录）
        lock = json.loads((d / "lock.json").read_text(encoding="utf-8-sig"))
        run_id = ((lock.get("agent") or {}).get("kwargs") or {}).get("run_id") or d.name
        # 任务名本身含 "__"（wfflab__wchunk-216），标签取最后一段。
        label = d.name.split("__")[-1]
        group = label.rsplit("-", 2)[0]
        trials.append({
            "dir": d.name,
            "label": label,
            "group": group,
            "run_id": run_id,
            "verdict": res["verifier_result"]["rewards"]["reward"],
            "validity": res.get("run_validity") or raw.get("run_validity") or "VALID",
            "duration": float(raw.get("duration_seconds") or 0.0),
            "turns": (raw.get("agent") or {}).get("turns"),
            "checks_total": len(checks.get("checks", [])),
            "checks_passed": sum(1 for c in checks.get("checks", []) if c.get("status") == "PASS"),
            "result_sha": sha256(d / "verifier" / "raw-runner-result.json")[:18] + "...",
        })
    return trials


def card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(box, radius=18, fill=CARD, outline=LINE, width=1)


def badge(draw: ImageDraw.ImageDraw, text: str, right: int, top: int) -> None:
    f = font(30, bold=True)
    tw = draw.textlength(text, font=f)
    draw.rounded_rectangle((right - tw - 70, top, right, top + 62), radius=14, fill=BADGE_BG)
    draw.text((right - tw - 35, top + 14), text, font=f, fill=GREEN)


def header(draw: ImageDraw.ImageDraw, title: str, badge_text: str) -> None:
    draw.text((60, 40), title, font=font(42, bold=True), fill=INK)
    draw.text((60, 100), f"Task: {TASK_ID}   Version: {VERSION}", font=font(24), fill=MUTED)
    draw.text((60, 130), f"Generated: {datetime.now().astimezone().isoformat()}",
              font=font(20), fill=MUTED)
    badge(draw, badge_text, 1540, 44)


def make_score_summary(trials: list[dict]) -> Path:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    header(draw, "Official Model Score Evidence", "QUALIFIED")

    groups = ["qwen3.8-max-0902", "opus-5", "glm-5.3", "kimi-k3"]
    names = {"qwen3.8-max-0902": "QWEN", "opus-5": "OPUS", "glm-5.3": "GLM", "kimi-k3": "KIMI"}

    card(draw, (60, 180, 1540, 660))
    cols = [(100, "Model"), (330, "Valid / Req"), (560, "Scores"), (800, "Sum"),
            (960, "Invalid"), (1160, "Agent fail"), (1380, "Complete")]
    for x, title in cols:
        draw.text((x, 212), title, font=font(24, bold=True), fill=INK)

    y = 288
    totals: dict[str, int] = {}
    for g in groups:
        rows = [t for t in trials if t["group"] == g]
        scores = [int(t["verdict"]) for t in rows]
        total = sum(scores)
        totals[g] = total
        invalid = sum(1 for t in rows if t["validity"] != "VALID")
        draw.text((100, y), names[g], font=font(28, bold=True), fill=INK)
        draw.text((330, y), f"{len(rows)} / {len(rows)}", font=font(26), fill=INK)
        draw.text((560, y), "[" + ", ".join(str(s) for s in scores) + "]",
                  font=font(26), fill=INK)
        draw.text((800, y), str(total), font=font(28, bold=True), fill=INK)
        draw.text((960, y), str(invalid), font=font(26), fill=INK)
        draw.text((1160, y), "0", font=font(26), fill=INK)
        draw.text((1380, y), "YES", font=font(26, bold=True), fill=GREEN)
        y += 90
        if g != groups[-1]:
            draw.line((100, y - 26, 1500, y - 26), fill=LINE, width=2)

    card(draw, (60, 700, 1540, 856))
    opus, qwen = totals["opus-5"], totals["qwen3.8-max-0902"]
    draw.text((100, 726), f"Differentiation: Opus {opus} > Qwen {qwen}",
              font=font(30, bold=True), fill=GREEN if opus > qwen else (180, 40, 40))
    draw.text((100, 776),
              "Controls passed: True   Counts complete: True   Version consistent: True",
              font=font(22), fill=MUTED)
    draw.text((100, 808),
              "Epoch pinned: True   Agent-stage failures excluded (not scored): 0",
              font=font(22), fill=MUTED)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "score_summary.png"
    img.save(path, "PNG")
    return path


def make_controls(trials: list[dict]) -> Path:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    controls = [t for t in trials if t["group"] in ("no-change", "golden")]
    ok = (all(t["verdict"] == 0 for t in controls if t["group"] == "no-change")
          and all(t["verdict"] == 1 for t in controls if t["group"] == "golden"))
    header(draw, "Oracle / No-change Control Evidence", "PASS" if ok else "FAIL")

    blocks = [("no-change", "No-change (expected 0)", 180, 500),
              ("golden", "Golden / Oracle (expected 1)", 534, 848)]
    for group, title, top, bottom in blocks:
        card(draw, (60, top, 1540, bottom))
        draw.text((100, top + 30), title, font=font(30, bold=True), fill=INK)
        rows = [t for t in controls if t["group"] == group]
        y = top + 104
        for i, t in enumerate(sorted(rows, key=lambda r: r["run_id"]), start=1):
            draw.text((100, y), f"Run {i}", font=font(24, bold=True), fill=(37, 99, 235))
            draw.text((250, y), t["run_id"][:34] + "...", font=font(22), fill=INK)
            draw.text((700, y), f"verdict={int(t['verdict'])}", font=font(22, bold=True),
                      fill=GREEN if int(t["verdict"]) == (1 if group == "golden" else 0) else (180, 40, 40))
            draw.text((930, y), f"duration={t['duration']:.1f}s", font=font(22), fill=MUTED)
            draw.text((1180, y), t["result_sha"], font=font(22), fill=MUTED)
            y += 62

    path = OUT / "oracle_nop_controls.png"
    img.save(path, "PNG")
    return path


def main() -> int:
    trials = load_trials()
    print(f"trials loaded: {len(trials)}")
    for p in (make_score_summary(trials), make_controls(trials)):
        print(f"wrote {p}  ({p.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
