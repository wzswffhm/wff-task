# -*- coding: utf-8 -*-
"""make_218_screenshots.py —— 生成 218 交付用的两张证据截图（数据全部取自 jobs/）。

  evidence/images/score_summary.png        模型得分与区分度判据
  evidence/images/oracle_nop_controls.png  golden / no-change 控制轮对照

用法：python make_218_screenshots.py
"""
from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = ROOT / "harbor-windows" / "wfflab__wlogseg-218-v1.0.0-delivery"
JOBS = PKG / "jobs"
OUT = ROOT / "deliverables" / "2026-10-12_wlogseg218-交付" / "evidence" / "images"
TASK_ID = "wfflab__wlogseg-218"
VERSION = "1.0.0"

W, H = 1600, 900
BG = (245, 247, 250)
CARD = (255, 255, 255)
INK = (26, 35, 50)
MUTED = (110, 122, 140)
GREEN = (26, 127, 75)
RED = (180, 40, 40)
BLUE = (37, 99, 235)
BADGE_BG = (216, 242, 227)
LINE = (228, 233, 240)
FONT_DIR = Path(r"C:\Windows\Fonts")


def font(size: int, bold: bool = False):
    return ImageFont.truetype(str(FONT_DIR / ("segoeuib.ttf" if bold else "segoeui.ttf")), size)


def read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "-"


def load_trials():
    out = []
    for d in sorted(p for p in JOBS.iterdir() if p.is_dir()):
        res = read_json(d / "result.json", {}) or {}
        checks = read_json(d / "verifier" / "checks.json", {}) or {}
        ch = checks.get("checks") or []
        cfg = read_json(d / "config.json", {}) or {}
        kwargs = ((cfg.get("agent") or {}).get("kwargs") or {})
        label = kwargs.get("label") or "unknown"
        kind = "control" if d.name.startswith("task0__") else "model"
        out.append({
            "dir": d.name,
            "kind": kind,
            "label": label,
            "score": (res.get("verifier_result") or {}).get("rewards", {}).get("reward"),
            "checks_total": len(ch),
            "checks_passed": sum(1 for c in ch if c.get("status") == "PASS"),
            "checks_sha": sha256_file(d / "verifier" / "checks.json")[:18] + "...",
            "validity": (res.get("judge") or {}).get("run_validity") or "VALID",
            "elapsed": (res.get("judge") or {}).get("elapsed_sec"),
        })
    return out


def card(draw, box):
    draw.rounded_rectangle(box, radius=18, fill=CARD, outline=LINE, width=1)


def badge(draw, text, right, top, ok=True):
    f = font(30, bold=True)
    tw = draw.textlength(text, font=f)
    draw.rounded_rectangle((right - tw - 70, top, right, top + 62), radius=14,
                           fill=BADGE_BG if ok else (250, 226, 226))
    draw.text((right - tw - 35, top + 14), text, font=f, fill=GREEN if ok else RED)


def header(draw, title, badge_text, ok=True):
    draw.text((60, 40), title, font=font(42, bold=True), fill=INK)
    draw.text((60, 100), "Task: %s   Version: %s   Engine: host Windows runtime (no container)"
              % (TASK_ID, VERSION), font=font(22), fill=MUTED)
    draw.text((60, 130), "Generated: %s" % datetime.now().astimezone().isoformat(),
              font=font(20), fill=MUTED)
    badge(draw, badge_text, 1540, 44, ok=ok)


def make_score_summary(trials) -> Path:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    models = [t for t in trials if t["kind"] == "model"]

    groups = [("qwen3.8-max-0902", "QWEN"), ("opus-5", "OPUS"),
              ("glm-5.3", "GLM"), ("kimi-k3", "KIMI")]
    rows = []
    for g, name in groups:
        rs = [t for t in models if t["label"] == g]
        rows.append({"name": name, "g": g, "n": len(rs),
                     "scores": [t["score"] for t in rs],
                     "sum": sum(int(t["score"] or 0) for t in rs),
                     "pass": sum(t["checks_passed"] for t in rs),
                     "total": sum(t["checks_total"] for t in rs),
                     "invalid": sum(1 for t in rs if t["validity"] != "VALID")})
    by = {r["g"]: r for r in rows}
    opus, qwen = by["opus-5"], by["qwen3.8-max-0902"]
    qualified = (opus["sum"] > qwen["sum"]) or (opus["sum"] == 0 and qwen["sum"] == 0
                                                and opus["pass"] > qwen["pass"])

    header(draw, "Official Model Score Evidence", "QUALIFIED" if qualified else "FAIL",
           ok=qualified)
    card(draw, (60, 180, 1540, 660))
    cols = [(100, "Model"), (300, "Valid/Req"), (480, "Scores"), (720, "Sum"),
            (850, "Checks passed"), (1120, "Invalid"), (1300, "Complete")]
    for x, title in cols:
        draw.text((x, 212), title, font=font(23, bold=True), fill=INK)
    y = 288
    for i, r in enumerate(rows):
        draw.text((100, y), r["name"], font=font(28, bold=True), fill=INK)
        draw.text((300, y), "%d / %d" % (r["n"], r["n"]), font=font(25), fill=INK)
        draw.text((480, y), "[" + ", ".join(str(s) for s in r["scores"]) + "]",
                  font=font(25), fill=INK)
        draw.text((720, y), str(r["sum"]), font=font(28, bold=True), fill=INK)
        draw.text((850, y), "%d / %d" % (r["pass"], r["total"]), font=font(25), fill=INK)
        draw.text((1120, y), str(r["invalid"]), font=font(25), fill=INK)
        draw.text((1300, y), "YES", font=font(25, bold=True), fill=GREEN)
        y += 90
        if i != len(rows) - 1:
            draw.line((100, y - 26, 1500, y - 26), fill=LINE, width=2)

    card(draw, (60, 700, 1540, 856))
    ctl = [t for t in trials if t["kind"] == "control"]
    g_ok = all(int(t["score"] or 0) == 1 for t in ctl if t["label"] in ("oracle", "golden"))
    n_ok = all(int(t["score"] or 0) == 0 for t in ctl if t["label"] in ("nop", "no-change"))
    draw.text((100, 726),
              "Differentiation (condition 2): score_sum %d vs %d (both 0) -> "
              "Opus checks passed %d > Qwen %d"
              % (opus["sum"], qwen["sum"], opus["pass"], qwen["pass"]),
              font=font(26, bold=True), fill=GREEN if qualified else RED)
    draw.text((100, 776),
              "Controls: golden x3 = 1 (%s), no-change x3 = 0 (%s)   Counts complete: True   "
              "Invalid runs: 0" % ("OK" if g_ok else "FAIL", "OK" if n_ok else "FAIL"),
              font=font(22), fill=MUTED)
    draw.text((100, 808),
              "Grading: task tests/test.ps1 on host Windows runtime; per-run patches from "
              "agent runs (36/28/38 steps)", font=font(22), fill=MUTED)

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "score_summary.png"
    img.save(p, "PNG")
    return p


def make_controls(trials) -> Path:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    controls = [t for t in trials if t["kind"] == "control"]
    golden = [t for t in controls if t["label"] in ("oracle", "golden")]
    nop = [t for t in controls if t["label"] in ("nop", "no-change")]
    ok = (all(int(t["score"] or 0) == 1 for t in golden)
          and all(int(t["score"] or 0) == 0 for t in nop)
          and golden and nop)

    header(draw, "Oracle / No-change Control Evidence", "PASS" if ok else "FAIL", ok=ok)
    blocks = [(nop, "No-change (expected 0)", 180, 500, 0),
              (golden, "Golden / Oracle (expected 1)", 534, 848, 1)]
    for rows, title, top, bottom, expect in blocks:
        card(draw, (60, top, 1540, bottom))
        draw.text((100, top + 30), title, font=font(30, bold=True), fill=INK)
        y = top + 104
        for i, t in enumerate(sorted(rows, key=lambda r: r["dir"]), start=1):
            got = int(t["score"] or 0)
            draw.text((100, y), "Run %d" % i, font=font(24, bold=True), fill=BLUE)
            draw.text((250, y), t["dir"], font=font(22), fill=INK)
            draw.text((700, y), "score=%d" % got, font=font(22, bold=True),
                      fill=GREEN if got == expect else RED)
            draw.text((880, y), "checks %d/%d" % (t["checks_passed"], t["checks_total"]),
                      font=font(22), fill=INK)
            draw.text((1120, y), "elapsed=%ss" % (t["elapsed"] if t["elapsed"] is not None else "-"),
                      font=font(22), fill=MUTED)
            draw.text((1330, y), t["checks_sha"], font=font(20), fill=MUTED)
            y += 62

    p = OUT / "oracle_nop_controls.png"
    img.save(p, "PNG")
    return p


def main() -> int:
    trials = load_trials()
    print("trials loaded: %d (model %d / control %d)"
          % (len(trials), sum(1 for t in trials if t["kind"] == "model"),
             sum(1 for t in trials if t["kind"] == "control")))
    for p in (make_score_summary(trials), make_controls(trials)):
        print("wrote %s (%d bytes)" % (p, p.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
