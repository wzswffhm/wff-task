#!/usr/bin/env python3
"""按 C1–C5 分级表核对题包的复杂度档位是否与硬指标自洽。

用法:
    python check_complexity.py <task-dir> [<task-dir> ...]
    python check_complexity.py --table            # 打印取值映射，便于与分级表对照
    python check_complexity.py --self-test        # 断言取值映射与分级表一致（改脚本后必跑）

背景：validate_task_package.py 只校验字段格式，不校验 task_complexity 与
文件数/产物数是否匹配。历史上出现过两类错误：
  ① 「凭感觉标 C4，实际文件数只有 14」的低报；
  ② 脚本自身把产物区间**压窄**（5–6 只认 C4），与分级表 C4=4–6 / C5=4–8 重叠的表述冲突，
     导致把合规的 C5 误判成 FAIL。本版按分级表区间取**并集**，并加 --self-test 防再次漂移。

分级表（外发版-基于weakness和skill 的数据构造方案 金融版 第 3 页）：
  文件数        C1=2   C2=5   C3=10  C4=25  C5=50+
  Requirement   C1=3   C2=6   C3=10  C4=15  C5=20
  输出产物数     C1=1-2 C2=2-3 C3=3-4 C4=4-6 C5=4-8   ← 相邻档区间重叠，落档取并集
  Evidence hop  C1=1   C2=2   C3=3   C4=4   C5=5
  工具种类数     C1=1   C2=2   C3=3   C4=4   C5=5+

判定口径（以分级表为准，脚本只是机械核对器）：
  1. 文件数 → 取满足 floor 的最高档（file_level）；
  2. 产物数 → 取区间包含该数值的**全部**档位（可重叠）；
  3. 申报档 > 文件数档：只要产物数支持该档即通过（大型项目/多产物例外），
     不要求把输入材料补到 25/50 个（补材料属改题，代价远高于改元数据）；
  4. 申报档 < 文件数档：低报，FAIL。

本脚本机械核对「文件数」与「输出产物数」两项；Requirement / hop / 工具种类需人工确认。
"""
import os
import re
import sys

ORDER = ["C1", "C2", "C3", "C4", "C5"]
FILE_FLOOR = {"C1": 2, "C2": 5, "C3": 10, "C4": 25, "C5": 50}
# 分级表原文的产物数区间（相邻档重叠，必须原样保留，不要"手改窄"）
ARTIFACT_RANGE = {"C1": (1, 2), "C2": (2, 3), "C3": (3, 4), "C4": (4, 6), "C5": (4, 8)}
# 自检用的期望值：产物数 -> 支持它的档位集合（区间取并集的结果）
EXPECTED_ARTIFACT_ALLOWED = {
    1: {"C1"},
    2: {"C1", "C2"},
    3: {"C2", "C3"},
    4: {"C3", "C4", "C5"},
    5: {"C4", "C5"},
    6: {"C4", "C5"},
    7: {"C5"},
    8: {"C5"},
}


def artifacts_allowed(count):
    """产物数落在哪些档：区间包含它的全部档位（重叠区取并集）。"""
    return {lvl for lvl, (lo, hi) in ARTIFACT_RANGE.items() if lo <= count <= hi}


def files_for_complexity(count):
    """文件数落在哪一档：取满足 floor 的最高档。"""
    level = "C1"
    for name in ORDER:
        if count >= FILE_FLOOR[name]:
            level = name
    return level


def print_table():
    print("产物数 -> 支持的档位（分级表区间取并集）")
    for n in sorted(EXPECTED_ARTIFACT_ALLOWED):
        got = artifacts_allowed(n)
        mark = "OK " if got == EXPECTED_ARTIFACT_ALLOWED[n] else "BAD"
        print(f"  {mark} {n}: {sorted(got, key=ORDER.index)}")
    print("\n文件数 -> 档位（取满足 floor 的最高档）")
    for n in (1, 2, 5, 9, 10, 12, 24, 25, 49, 50):
        print(f"      {n}: {files_for_complexity(n)}")


def self_test():
    bad = []
    for n, expect in EXPECTED_ARTIFACT_ALLOWED.items():
        if artifacts_allowed(n) != expect:
            bad.append((n, sorted(artifacts_allowed(n)), sorted(expect)))
    if bad:
        print("[FAIL] 取值映射与分级表不一致：")
        for n, got, exp in bad:
            print(f"        产物数 {n}: 实得 {got}，应为 {exp}")
        print("        常见原因：ARTIFACT_RANGE 被改窄（如把 C5 的 4–8 写成 7–8）。")
        return 1
    print("[PASS] 取值映射与分级表一致（产物区间按并集，含 4–6 的 C4/C5 重叠）。")
    return 0


def read_toml(path):
    return open(path, encoding="utf-8").read()


def check(task_dir):
    task_dir = task_dir.rstrip("/\\")
    toml_path = os.path.join(task_dir, "task.toml")
    if not os.path.isfile(toml_path):
        print(f"[FAIL] {task_dir}: 缺少 task.toml")
        return 1
    toml = read_toml(toml_path)

    declared = re.search(r'task_complexity\s*=\s*"(C\d)"', toml)
    declared = declared.group(1) if declared else None

    artifact_block = re.search(r"artifacts\s*=\s*\[(.*?)\]", toml, re.S)
    outputs = re.findall(r'"(/app/output/[^"]+)"', artifact_block.group(1)) if artifact_block else []
    n_outputs = len(outputs)

    input_dir = os.path.join(task_dir, "environment", "input_files")
    n_files = len([f for f in os.listdir(input_dir)
                   if os.path.isfile(os.path.join(input_dir, f))]) if os.path.isdir(input_dir) else 0

    file_level = files_for_complexity(n_files)
    artifact_ok = artifacts_allowed(n_outputs)

    fails = []
    if declared is None:
        fails.append("task.toml 缺 task_complexity")
    else:
        if ORDER.index(declared) < ORDER.index(file_level):
            fails.append(
                f"文件数 {n_files} 对应 {file_level}，但声明为 {declared}"
                f"（低报：应至少 {file_level}）")
        if ORDER.index(declared) > ORDER.index(file_level):
            # 申报档高于文件数档：只要产物数支持该档即通过（大型项目/多产物例外）
            if declared not in artifact_ok:
                fails.append(
                    f"文件数 {n_files} 只支持 {file_level}，声明 {declared} 需要更高文件数"
                    f"（C4 需 25 个、C5 需 50 个），且产物数 {n_outputs} 也不支持 {declared}")
        if declared not in artifact_ok:
            fails.append(
                f"输出产物数 {n_outputs} 支持 {sorted(artifact_ok, key=ORDER.index) or '无档位'}，"
                f"与声明的 {declared} 不匹配")

    head = "[PASS]" if not fails else "[FAIL]"
    print(f"{head} {os.path.basename(task_dir)}  "
          f"文件数={n_files}→{file_level}  产物数={n_outputs}→{sorted(artifact_ok, key=ORDER.index)}  "
          f"声明={declared}")
    for f in fails:
        print("        - " + f)
    if fails and n_outputs in (4, 5, 6) and declared == "C5":
        print("        - 提示：产物数 4–6 同时落在 C4(4–6) 与 C5(4–8) 区间内，"
              "此处 FAIL 只可能来自文件数维度或脚本取值漂移，"
              "先跑 --self-test，再按分级表复核申报依据")
    print("        NOTE: Requirement / evidence-hop / 工具种类数需人工核对"
          "（判据条数可作 Requirement 的近似参考）")
    return 1 if fails else 0


if __name__ == "__main__":
    flags = {a for a in sys.argv[1:] if a.startswith("-")}
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--table" in flags:
        print_table()
        sys.exit(0)
    if "--self-test" in flags:
        sys.exit(self_test())
    if not args:
        raise SystemExit(__doc__)
    rc = 0
    for d in args:
        rc |= check(d)
    print(f"\nFAIL 合计: {rc}")
    sys.exit(rc)
