# -*- coding: utf-8 -*-
"""生成 wfflab__wspawn-218 的分数汇总截图（飞书「分数截图」字段用）。"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "score_summary.png"

W, H = 1280, 720
BG = (255, 255, 255)
FG = (24, 28, 36)
MUTED = (110, 118, 132)
ACCENT = (28, 96, 200)
OK = (18, 140, 70)
BAD = (196, 48, 48)
GRID = (222, 226, 234)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]


def font(size, bold=False):
    paths = FONT_CANDIDATES if not bold else [FONT_CANDIDATES[1], FONT_CANDIDATES[0], FONT_CANDIDATES[2]]
    for p in paths:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

f_title = font(34, True)
f_sub = font(18)
f_head = font(20, True)
f_cell = font(19)
f_small = font(16)

x0, y0 = 56, 48
d.text((x0, y0), "wfflab__wspawn-218  模型区分度与对照结果", font=f_title, fill=FG)
d.text((x0, y0 + 52), "Windows / NTFS 稀疏文件与簇分配 · required 20（F2P 10 / P2P 10）· 二值判分",
       font=f_sub, fill=MUTED)

# ---- 表头
tx, ty = x0, y0 + 108
cols = [("模型 / 对照", 300), ("三轮得分", 300), ("总分", 130), ("testcase 累计", 180), ("判定", 180)]
head_h = 46
d.rectangle([tx, ty, tx + sum(c[1] for c in cols), ty + head_h], fill=(242, 245, 250))
cx = tx
for name, w in cols:
    d.text((cx + 16, ty + 12), name, font=f_head, fill=FG)
    cx += w
    d.line([cx, ty, cx, ty + head_h], fill=GRID)

rows = [
    ("Qwen3.8-Max-0902 ×3", "[1, 0, 1]", "2", "58", ("次要模型", MUTED)),
    ("Opus 5 (claude-opus-5) ×3", "[1, 1, 1]", "3", "60", ("区分度成立", OK)),
    ("Oracle（参考解）×3", "[1, 1, 1]", "3", "60", ("预期 1（符合）", OK)),
    ("no-change（缺陷版）×3", "[0, 0, 0]", "0", "30", ("预期 0（符合）", OK)),
]
row_h = 48
ry = ty + head_h
for i, (label, scores, total, tc, (verdict, color)) in enumerate(rows):
    if i % 2 == 1:
        d.rectangle([tx, ry, tx + sum(c[1] for c in cols), ry + row_h], fill=(250, 251, 253))
    vals = [label, scores, total, tc, verdict]
    cx = tx
    for (name, w), v in zip(cols, vals):
        use = color if name == "判定" else FG
        d.text((cx + 16, ry + 13), v, font=f_cell, fill=use)
        cx += w
        d.line([cx, ry, cx, ry + row_h], fill=GRID)
    d.line([tx, ry, tx + sum(c[1] for c in cols), ry], fill=GRID)
    ry += row_h
d.line([tx, ry, tx + sum(c[1] for c in cols), ry], fill=GRID)
d.line([tx, ty, tx, ry], fill=GRID)
d.line([tx + sum(c[1] for c in cols), ty, tx + sum(c[1] for c in cols), ry], fill=GRID)

# ---- 结论
cy = ry + 40
d.rectangle([x0, cy, x0 + 1160, cy + 150], fill=(244, 249, 245), outline=(206, 226, 210))
d.text((x0 + 24, cy + 18), "区分度门禁：PASS", font=f_head, fill=OK)
lines = [
    "Opus 总分 3 > Qwen 总分 2；且 Opus testcase 累计 60 > Qwen 58",
    "windows-harbor-qc 结论 PASS：交付目录 / 模型门禁 / 模型 jobs / Oracle-NOP / 十项人工复核 全 PASS",
    "12 个 Harbor 原生 job 的 task_checksum 唯一：575341f7d6aff81bc358b125e31d8fa12090c8f1743f9c630fd9677ca056688f",
    "本批口径 REQUIRED_COUNTS = {qwen: 3, opus: 3}，不跑 GLM / Kimi",
]
for i, t in enumerate(lines):
    d.text((x0 + 24, cy + 54 + i * 24), t, font=f_small, fill=FG)

d.text((x0, H - 44), "生成于 2026-10-14 · 数据来源 jobs/model-{qwen,opus}-{1,2,3} 与 jobs/ctl-{oracle,nop}-{1,2,3}",
       font=f_small, fill=MUTED)

img.save(OUT)
print("saved", OUT, img.size)
