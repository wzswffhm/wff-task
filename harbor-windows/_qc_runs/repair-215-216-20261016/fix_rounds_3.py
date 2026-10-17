# -*- coding: utf-8 -*-
"""口径定稿：Qwen / Opus 各只跑 3 轮，jobs/ 直接放 3+3+3+3 = 12 个 job。

改动：
  1. run_*_model_rounds.py 的 ROUNDS 回到 3/3；
  2. assemble_*_harbor_jobs.py 去掉“第 N 轮另存 evidence”的分流逻辑，全部组装进 jobs/。
"""
from __future__ import annotations

import pathlib

HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
BUILDS = ["wsparse-build", "wvas-build"]
MODS = {"wsparse-build": "wsparse", "wvas-build": "wvas"}

OLD_ROUNDS = '''# 甲方 2026-10-16 质检指南第十节：统计口径与难度卡点都以「4 次 qwen3.8-max
# rollout」为准，因此两个模型各跑 4 轮。
ROUNDS = [("qwen", "qwen3.8-max", 4), ("opus", "opus-5", 4)]'''
NEW_ROUNDS = '''# 交付方 2026-10-16 口径：Qwen 与 Opus 各跑 3 轮，jobs/ 直接放 3+3+3+3 = 12 个 job，
# 不做任何轮次筛选。
ROUNDS = [("qwen", "qwen3.8-max", 3), ("opus", "opus-5", 3)]'''

OLD_BLOCK_START = "    control_trials = ["
OLD_BLOCK_END = "    if a.dry_run:"


def patch_rounds(path: pathlib.Path) -> None:
    text = path.read_text(encoding="utf-8")
    if NEW_ROUNDS in text:
        print("rounds already 3/3:", path.name)
        return
    if OLD_ROUNDS in text:
        path.write_text(text.replace(OLD_ROUNDS, NEW_ROUNDS), encoding="utf-8")
        print("patched rounds:", path.name)
    else:
        print("!! rounds pattern not found:", path.name)


def patch_assemble(path: pathlib.Path) -> None:
    text = path.read_text(encoding="utf-8")
    head, sep, tail = text.partition(OLD_BLOCK_START)
    if not sep:
        print("!! assemble block not found:", path.name)
        return
    _, sep2, rest = tail.partition(OLD_BLOCK_END)
    if not sep2:
        print("!! assemble block end not found:", path.name)
        return
    new_block = (
        "    trials = ([(name, path, \"oracle\" if \"-oracle-\" in name else \"nop\")\n"
        "               for name, path in find_trials(CONTROL_JOBS)]\n"
        "              + [(name, path, \"model\") for name, path in find_trials(MODEL_JOBS)])\n"
        "    print(\"发现 trial：控制轮 %d + 模型轮 %d = %d\"\n"
        "          % (len(find_trials(CONTROL_JOBS)), len(find_trials(MODEL_JOBS)), len(trials)))\n"
    )
    text = head + new_block + OLD_BLOCK_END + rest
    # 移除第 N 轮另存 evidence 的代码块
    marker = "    # ---- 第 4 轮模型记录：随包交付但不进 jobs/ ------------------------------"
    marker2 = "    # ---- 第 4 轮模型记录"
    idx = text.find(marker2)
    if idx == -1:
        idx = text.find(marker)
    if idx != -1:
        stop = text.find("    ok = sum(", idx)
        if stop != -1:
            text = text[:idx] + text[stop:]
    path.write_text(text, encoding="utf-8")
    print("patched assemble:", path.name)


def main() -> int:
    for build in BUILDS:
        mod = MODS[build]
        patch_rounds(HW / "_qc_runs" / build / f"run_{mod}_model_rounds.py")
        patch_assemble(HW / "_qc_runs" / build / f"assemble_{mod}_harbor_jobs.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
