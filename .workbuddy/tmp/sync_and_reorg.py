# -*- coding: utf-8 -*-
"""同步修复后的题包到交付批次，并按质检报告第 7 条重组归档树。

质检报告（序号 239）第 7 条：
  「ZIP 第二层混放 交付文档.md、批次级 跑分产物与轨迹/ 与题目目录，题目目录本身缺少这两项，
    不符合当前归档树；请将交付文档和四执行体证据归入 FIN3-WKN-150/，
    保证顶层同名目录下第二层仅为独立题目目录。」

目标结构：
  <批次目录>/
  └── FIN3-WKN-150/                 ← 第二层唯一
      ├── instruction.md / task.toml / rubrics.json / environment / solution / tests
      ├── 交付文档.md                ← 由批次级移入
      └── 跑分产物与轨迹/             ← 由批次级移入（三模型 output 原样保留，仅同步 oracle 金标）

用法：python sync_and_reorg.py [--dry-run]
"""
import os
import shutil
import sys

REPO = r"C:\Users\Administrator\Desktop\wff-task"
SRC_TASK = os.path.join(REPO, "harbor-weakness", "FIN3-WKN-150")
BATCHES = [
    os.path.join(REPO, "harbor-weakness", "work_fin-b01_20261006_fix3-150"),
    os.path.join(REPO, "harbor-weakness", "work-金融-私募股权投资-20261008"),
]
TASK_NAME = "FIN3-WKN-150"
GOLDEN_FILES = ["FIN3-WKN-150_PreIPO投资决策备忘录.md", "FIN3-WKN-150_reproduce.py"]

dry = "--dry-run" in sys.argv


def copy_tree(src, dst, label):
    """把 src 内容同步到 dst（覆盖同名，保留 dst 独有的其它文件）。"""
    n = 0
    for dirpath, _dirnames, filenames in os.walk(src):
        rel = os.path.relpath(dirpath, src)
        target_dir = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target_dir, exist_ok=True)
        for name in filenames:
            s = os.path.join(dirpath, name)
            d = os.path.join(target_dir, name)
            if os.path.isfile(d) and open(s, "rb").read() == open(d, "rb").read():
                continue
            if not dry:
                shutil.copy2(s, d)
            n += 1
    print(f"    {label}: 同步 {n} 个文件")


for batch in BATCHES:
    print("=" * 88)
    rel_batch = os.path.relpath(batch, REPO)
    if not os.path.isdir(batch):
        print(f"[缺失批次] {rel_batch}")
        continue
    print(rel_batch)
    task_dir = os.path.join(batch, TASK_NAME)

    # ① 同步题包本体 → 批次内题目目录
    if os.path.isdir(task_dir):
        copy_tree(SRC_TASK, task_dir, "题目目录")
    else:
        print(f"    !! 批次内无 {TASK_NAME}/，跳过")

    # ② 重组：把批次级的 交付文档.md 与 跑分产物与轨迹/ 移入题目目录
    for item in ("交付文档.md", "跑分产物与轨迹"):
        src_item = os.path.join(batch, item)
        dst_item = os.path.join(task_dir, item)
        if not os.path.exists(src_item):
            print(f"    [跳过] {item}（批次级不存在）")
            continue
        if os.path.exists(dst_item):
            print(f"    [提示] {item} 已在题目目录内，删除批次级残留")
            if not dry:
                if os.path.isdir(src_item):
                    shutil.rmtree(src_item)
                else:
                    os.remove(src_item)
            continue
        print(f"    移入: {item} -> {TASK_NAME}/")
        if not dry:
            shutil.move(src_item, dst_item)

    # ③ 同步 oracle 输出（金标副本，报告第 4 条要求）
    oracle_out = os.path.join(task_dir, "跑分产物与轨迹", "oracle", "output")
    if os.path.isdir(oracle_out):
        n = 0
        for name in GOLDEN_FILES:
            s = os.path.join(SRC_TASK, "solution", "golden_output", name)
            d = os.path.join(oracle_out, name)
            if os.path.isfile(s) and (not os.path.isfile(d) or open(s, "rb").read() != open(d, "rb").read()):
                if not dry:
                    shutil.copy2(s, d)
                n += 1
        print(f"    oracle/output 金标同步: {n} 个文件")

    # ④ 结构校验
    print("    重组后结构:")
    for entry in sorted(os.listdir(batch)):
        print(f"      {entry}")
    if os.path.isdir(task_dir):
        print(f"      └── {TASK_NAME}/: {sorted(os.listdir(task_dir))}")
print()
print("（dry-run 未落盘）" if dry else "完成")
