#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIN3-WKN-152 打包：批次包 + task/answer 拆分包。

要点（对应历史返修教训）：
- 层级：批次目录 → 题目目录 → 五件套（不得平铺、不得多套一层）
- solve.sh / test.sh 显式写 external_attr = 0o755（Windows 重新压缩会清零）
- 全部文本文件保持 LF（zip 内不做转换）
- 排除残留：__pycache__ / .git / .venv / __MACOSX / .DS_Store / reward*.json / logs / jobs
"""
from __future__ import annotations

import os
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path("harbor-weakness")
TASK = "FIN3-WKN-152"
BATCH = sys.argv[1] if len(sys.argv) > 1 else "work_fin-b01_20261009-152"
OUT = REPO / "_qc_runs" / "packages"
OUT.mkdir(parents=True, exist_ok=True)

EXCLUDE_NAMES = {".git", "__pycache__", ".venv", "__MACOSX", ".DS_Store",
                 "reward.json", "reward-details.json", "logs", "jobs",
                 "reward_exit_message.json"}
EXEC_FILES = {"solve.sh", "test.sh"}
# answer 包内容 = solution/ + tests/__golden_output/
ANSWER_DIRS = ("solution",)
ANSWER_TEST_SUB = "__golden_output"


def exclude(p: pathlib.Path) -> bool:
    return any(part in EXCLUDE_NAMES for part in p.parts)


def add(zf: zipfile.ZipFile, src: pathlib.Path, arc: str, executable: bool = False):
    zi = zipfile.ZipInfo.from_file(src, arc)
    mode = 0o755 if executable else 0o644
    zi.external_attr = (mode & 0xFFFF) << 16
    zi.compress_type = zipfile.ZIP_DEFLATED
    with open(src, "rb") as f:
        zf.writestr(zi, f.read())


def task_files(root: pathlib.Path):
    """五件套中进 task 包的文件。

    对齐 FIN3-WKN-151（序号 267，一审通过）的拆分口径：
    task 包不含 solution/，也不含 tests/__golden_output/（参考答案归 answer 包）。
    """
    for p in sorted(root.rglob("*")):
        if not p.is_file() or exclude(p.relative_to(root)):
            continue
        rel = p.relative_to(root)
        if rel.parts[0] == "solution":
            continue
        if rel.parts[0] == "tests" and len(rel.parts) > 1 and rel.parts[1] == ANSWER_TEST_SUB:
            continue
        yield p, rel


def answer_files(root: pathlib.Path):
    """solution/ + tests/__golden_output/。"""
    for p in sorted(root.rglob("*")):
        if not p.is_file() or exclude(p.relative_to(root)):
            continue
        rel = p.relative_to(root)
        if rel.parts[0] == "solution":
            yield p, rel
        elif rel.parts[0] == "tests" and len(rel.parts) > 2 and rel.parts[1] == ANSWER_TEST_SUB:
            yield p, rel


def build():
    src = REPO / TASK
    results = []

    # ---- 1) 批次包：批次目录根文件（交付文档/跑分产物）+ 题目目录（五件套）----
    bp = OUT / f"{BATCH}.zip"
    bdir = REPO / BATCH          # 批次目录（交付文档.md、跑分产物与轨迹/ 等）
    with zipfile.ZipFile(bp, "w") as zf:
        # 1a. 批次根文件与批次级目录（交付文档、跑分产物与轨迹）
        if bdir.is_dir():
            for p in sorted(bdir.rglob("*")):
                if not p.is_file() or exclude(p.relative_to(bdir)):
                    continue
                rel = p.relative_to(bdir)
                if rel.parts[0] == TASK:      # 题目目录由下方统一打包
                    continue
                add(zf, p, f"{BATCH}/{rel.as_posix()}", executable=p.name in EXEC_FILES)
        # 1b. 题目目录（五件套）
        for p in sorted(src.rglob("*")):
            if not p.is_file() or exclude(p.relative_to(src)):
                continue
            rel = p.relative_to(src)
            arc = f"{BATCH}/{TASK}/{rel.as_posix()}"
            add(zf, p, arc, executable=p.name in EXEC_FILES)
    results.append(bp)

    # ---- 2) task 包 ----
    tp = OUT / f"{TASK}_task.zip"
    with zipfile.ZipFile(tp, "w") as zf:
        for p, rel in task_files(src):
            add(zf, p, f"{TASK}/{rel.as_posix()}", executable=p.name in EXEC_FILES)
    results.append(tp)

    # ---- 3) answer 包 ----
    ap = OUT / f"{TASK}_answer.zip"
    with zipfile.ZipFile(ap, "w") as zf:
        for p, rel in answer_files(src):
            add(zf, p, f"{TASK}/{rel.as_posix()}", executable=p.name in EXEC_FILES)
    results.append(ap)

    # ---- 校验 ----
    print("=" * 90)
    for z in results:
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
            bad = [n for n in names if any(x in n for x in EXCLUDE_NAMES)]
            execs = [n for n in names if n.rsplit("/", 1)[-1] in EXEC_FILES]
            modes = {}
            for n in execs:
                modes[n] = (zf.getinfo(n).external_attr >> 16) & 0o777
            depth_ok = all(n.split("/")[0] in (BATCH, TASK) for n in names)
            print(f"\n{z.name}  ({z.stat().st_size:,} B, {len(names)} entries)")
            print(f"  层级根正确: {depth_ok}   残留: {bad if bad else '无 ✓'}")
            print(f"  可执行位: {modes if modes else '(无 sh)'}")
            top = sorted({n.split('/')[0] for n in names})
            print(f"  顶层条目: {top}")
    # golden 双份在批次包内一致
    with zipfile.ZipFile(bp) as zf:
        g = {n.split("/", 2)[-1]: zf.read(n) for n in zf.namelist()
             if "/solution/golden_output/" in n or "/tests/__golden_output/" in n}
        a = {k: v for k, v in g.items() if k in [x.split("/", 1)[-1] for x in zf.namelist() if "/solution/golden_output/" in x]}
    print("\n" + "=" * 90)
    print("打包完成")


if __name__ == "__main__":
    build()
