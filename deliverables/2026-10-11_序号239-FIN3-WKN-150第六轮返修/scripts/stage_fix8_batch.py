# -*- coding: utf-8 -*-
"""组建 fix8 批次：题目五件套 + 三模型复用归档 + Oracle 真实生成产物与执行证据。

对应质检报告（序号 239 第六版）第 5/6 项：
  - 参考生成脚本最小修正后，Oracle 七件产物改为「由脚本从只读输入真实生成」的产物；
  - 生成过程（命令 / 日志 / 耗时 / 产物哈希）作为可核验执行归档随包交付；
  - 三模型候选产物与判分无需重跑，按报告第 4 项沿用 fix7 归档值。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
H = REPO / "harbor-weakness"
SRC_TASK = H / "FIN3-WKN-150"
FIX7 = H / "work_fin-b01_20261006_fix7-150" / "FIN3-WKN-150"
BATCH = H / "work_fin-b01_20261006_fix8-150"
DST_TASK = BATCH / "FIN3-WKN-150"
GEN = (REPO / "deliverables" / "2026-10-11_序号239-FIN3-WKN-150第六轮返修"
       / "evidence" / "oracle_generation")
MODELS = ["qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
EXCLUDE_DIRS = {"_rejudge", "__pycache__"}
EXCLUDE_FILES = {"交付文档.md"}


def ignore(directory: str, names: list[str]) -> set[str]:
    """排除判分暂存（含 _rejudge*/）、缓存与题目目录内不应随包交付的文件。"""
    return {n for n in names
            if n in EXCLUDE_DIRS or n in EXCLUDE_FILES or n.startswith("_rejudge")}

ORACLE_NOTE = """oracle 试次说明（第六轮，批次 work_fin-b01_20261006_fix8-150）
============================================================
本目录的七件产物**由参考生成脚本从只读输入材料真实生成**，不是复制 golden 冒充：

  生成入口：python3 /solution/golden_output/FIN3-WKN-150_reproduce.py /app/input_files /app/output
  运行镜像：fin3-wkn-150:local（Python 3.12 / numpy 2.5.3 / pandas 3.0.6 / matplotlib 3.11.2）
  输入目录：environment/input_files/（40 份材料，只读挂载）
  生成产物：1 份备忘录 + 1 份复算代码 + 5 张复合图 PNG（共 7 项）

为回应质检报告第 5 项，solution/golden_output/FIN3-WKN-150_reproduce.py 的字符串插值
已做**最小修正**（备忘录退出回报段的 4 个片段补 f 前缀，原先会输出 {med_pe:.2f} 等字面占位符），
tests/__golden_output/ 的镜像同步为逐字节一致；两份 golden 的备忘录同时更新为本次生成结果，
使「归档金标」与「生成脚本输出」严格同源（sha256 见 generated_manifest.json）。

solution/solve.sh 属平台固定模板（97 B / sha256 3f26ac81cb1c4583…，与 FIN3-WKN-149 等题逐字节一致），
本轮**未改动**，以免破坏平台模板一致性；生成证据改由本目录承载。

本目录文件：
  - output/                    Oracle 七件产物（真实生成）
  - 轨迹/generation.log        生成过程 stdout（脚本完整输出）
  - 轨迹/generation.json       生成命令、镜像、返回码、耗时
  - 轨迹/generated_manifest.json  七件产物的尺寸与 sha256
  - 轨迹/说明.txt              本说明
评分结果见 ../reward.json 与 ../reward-details.json。
"""


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if BATCH.exists():
        shutil.rmtree(BATCH)
    DST_TASK.mkdir(parents=True)

    # 1) 题目五件套（含修正后的 golden / rubrics.toml，solve.sh 为平台模板）
    shutil.copytree(SRC_TASK, DST_TASK, dirs_exist_ok=True, ignore=ignore)
    print(f"题目目录已复制 -> {DST_TASK}")

    # 版本：源题目目录已升为 1.0.8；此处仅校验，避免改写引入换行差异
    toml = DST_TASK / "task.toml"
    text = toml.read_text(encoding="utf-8")
    if 'version = "1.0.8"' not in text:
        raise SystemExit("task.toml 版本不是 1.0.8")
    if b"\r\n" in toml.read_bytes():
        raise SystemExit("task.toml 含 CRLF")
    print("task.toml version = 1.0.8（LF）")

    archive = DST_TASK / "跑分产物与轨迹"
    archive.mkdir(parents=True)

    # 2) 三模型：复用 fix7 归档（报告第 4 项：无需重跑）
    for model in MODELS:
        shutil.copytree(FIX7 / "跑分产物与轨迹" / model, archive / model, dirs_exist_ok=True)
        print(f"三模型归档复用 {model}")

    # 3) oracle：轨迹沿用，output 换为真实生成产物
    oracle = archive / "oracle"
    (oracle / "轨迹").mkdir(parents=True)
    for name in ["说明.txt", "oracle.txt", "trial.log"]:
        src = FIX7 / "跑分产物与轨迹" / "oracle" / "轨迹" / name
        if src.is_file():
            shutil.copy2(src, oracle / "轨迹" / name)
    (oracle / "轨迹" / "说明.txt").write_text(ORACLE_NOTE, encoding="utf-8")
    shutil.copytree(GEN / "output", oracle / "output", dirs_exist_ok=True)
    for src, dst in [
        (GEN / "logs" / "generate.log", oracle / "轨迹" / "generation.log"),
        (GEN / "logs" / "docker_result.json", oracle / "轨迹" / "generation.json"),
        (GEN / "generated_manifest.json", oracle / "轨迹" / "generated_manifest.json"),
        (GEN / "generated_manifest.json", oracle / "轨迹" / "generated_manifest.json"),
    ]:
        if src.is_file():
            shutil.copy2(src, dst)
    print("oracle output + 生成执行证据已写入")

    # 4) summary（先沿用 fix7，重判后回填 oracle 分数）
    shutil.copy2(FIX7 / "跑分产物与轨迹" / "summary.json", archive / "summary.json")

    print("\n=== 产物核验 ===")
    out = sorted(p.name for p in (oracle / "output").rglob("*") if p.is_file())
    print(f"oracle output 文件数: {len(out)}")
    for name in out:
        print("   ", name)
    memo = oracle / "output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md"
    print(f"\noracle memo sha: {sha256(memo)[:16]}  size={memo.stat().st_size:,}")
    gold = DST_TASK / "solution" / "golden_output" / "FIN3-WKN-150_PreIPO投资决策备忘录.md"
    print(f"golden memo sha: {sha256(gold)[:16]}  size={gold.stat().st_size:,}")
    print(f"同源一致: {sha256(memo) == sha256(gold)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
