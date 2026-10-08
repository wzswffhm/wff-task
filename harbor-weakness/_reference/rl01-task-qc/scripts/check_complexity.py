#!/usr/bin/env python3
"""按 C1–C5 分级表核对题包的复杂度档位是否与硬指标自洽。

用法: python check_complexity.py <task-dir> [<task-dir> ...]

背景：validate_task_package.py 只校验字段格式，不校验 task_complexity 与
文件数/产物数是否匹配。历史上出现过「凭感觉标 C4，实际文件数只有 14」的
退回风险，故补这一道机械门禁。

分级表（外发版-基于weakness和skill 的数据构造方案 金融版 第 3 页）：
  文件数        C1=2  C2=5   C3=10  C4=25  C5=50+
  Requirement   C1=3  C2=6   C3=10  C4=15  C5=20
  输出产物数     C1=1-2 C2=2-3 C3=3-4 C4=4-6 C5=4-8
  Evidence hop  C1=1  C2=2   C3=3   C4=4   C5=5
  工具种类数     C1=1  C2=2   C3=3   C4=4   C5=5+

本脚本机械核对「文件数 / 输出产物数 / Requirement（判据条数近似）/ 工具种类数」四项，
Evidence hop 无法机械计算，仍须人工核对。

本地增量（2026-10-01，与上游 verbatim 版的差异）：
规范的分级是**多指标综合**，不是「文件数单项定档」。上游版本只按 input_files 的文件数
判档，一个 4 份材料、35 条判据、3-hop 推理的法律题会被判成「文件数 4 只支持 C1」而误报
阻断（真实案例：LAW-002 / LAW-004 标 C3 被判 FAIL，甲方并未退回）。现改为：
  1. 逐指标算各自支持的档位，取最高档 max_supported 与最低档 min_supported；
  2. 声明档位高于 max_supported（无任何指标支撑）→ FAIL（虚标）；
  3. 声明档位低于 min_supported（所有指标都更高）→ NOTE 低报，交人工确认；
  4. 落在区间内 → PASS，并逐指标打印档位供人工核 evidence-hop。
"""
import os
import re
import sys

ORDER = ["C1", "C2", "C3", "C4", "C5"]
FILE_FLOOR = {"C1": 2, "C2": 5, "C3": 10, "C4": 25, "C5": 50}
# Requirement（判据条数近似）与工具种类数的档位下限
REQ_FLOOR = {"C1": 3, "C2": 6, "C3": 10, "C4": 15, "C5": 20}
TOOL_FLOOR = {"C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5}
# 产物数 → 允许的档位集合（相邻档位在边界值上重叠，故用集合）
ARTIFACT_ALLOWED = {
    1: {"C1"}, 2: {"C1"},
    3: {"C2", "C3"},
    4: {"C3", "C4"},
    5: {"C4"}, 6: {"C4"},
    7: {"C5"}, 8: {"C5"},
}


def files_for_complexity(count):
    """按 floor 表判定该计数支持的档位：取满足 floor 的最高档。"""
    return level_for(count, FILE_FLOOR)


def level_for(count, floor):
    level = None
    for name in ORDER:
        if count >= floor[name]:
            level = name
    return level


def artifact_levels(n):
    """输出产物数支持的档位集合。"""
    return ARTIFACT_ALLOWED.get(n, set())


def highest(levels):
    """取集合/序列里最高的档位，空则 None。"""
    got = [x for x in levels if x in ORDER]
    return max(got, key=ORDER.index) if got else None


def count_criteria(task_dir):
    """判据条数（Requirement 的近似）：优先 rubrics.json，回退 tests/rubrics.toml。"""
    import json
    path = os.path.join(task_dir, "rubrics.json")
    if os.path.isfile(path):
        try:
            raw = json.load(open(path, encoding="utf-8"))
            items = raw["items"] if isinstance(raw, dict) else raw
            return len(items)
        except Exception:  # noqa: BLE001
            pass
    path = os.path.join(task_dir, "tests", "rubrics.toml")
    if os.path.isfile(path):
        return read_toml(path).count("[[criterion]]")
    return 0


def count_tools(toml):
    """task.toml 的 tool_set 长度（工具种类数的近似）。"""
    m = re.search(r"tool_set\s*=\s*\[(.*?)\]", toml, re.S)
    if not m:
        return 0
    return len(re.findall(r'"[^"]+"', m.group(1)))


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

    n_req = count_criteria(task_dir)
    n_tools = count_tools(toml)

    file_level = files_for_complexity(n_files)
    art_level = highest(artifact_levels(n_outputs))
    req_level = level_for(n_req, REQ_FLOOR)
    tool_level = level_for(n_tools, TOOL_FLOOR)

    metrics = [
        ("文件数", n_files, file_level),
        ("产物数", n_outputs, art_level),
        ("Requirement(判据条数近似)", n_req, req_level),
        ("工具种类数", n_tools, tool_level),
    ]
    supported = [lvl for _, _, lvl in metrics if lvl]
    max_supported = highest(supported)
    min_supported = min(supported, key=ORDER.index) if supported else None

    fails = []
    notes = []
    if declared is None:
        fails.append("task.toml 缺 task_complexity")
    elif max_supported is None:
        fails.append("四个可机械指标都为 0，无法核对 task_complexity")
    elif ORDER.index(declared) > ORDER.index(max_supported):
        fails.append(
            f"声明 {declared} 高于全部指标的支持上限 {max_supported}"
            f"（逐指标：{', '.join(f'{k}={v}' for k, _, v in metrics)}）→ 虚标，"
            f"应改题补材料或按实测档位标注")
    elif ORDER.index(declared) < ORDER.index(min_supported):
        notes.append(
            f"声明 {declared} 低于全部指标的下限 {min_supported}"
            f"（逐指标：{', '.join(f'{k}={v}' for k, _, v in metrics)}）→ 低报，"
            f"请人工确认是否需要上调（会影响 C1–C5 配额分布）")
    else:
        lower = [k for k, _, v in metrics if v and ORDER.index(v) < ORDER.index(declared)]
        if lower:
            notes.append(
                f"单项指标低于声明档位：{', '.join(lower)}"
                f"（逐指标：{', '.join(f'{k}={v}' for k, _, v in metrics)}）"
                f"→ 声明 {declared} 靠其余指标支撑，请人工核 evidence-hop 是否确达 {declared}")

    head = "[PASS]" if not fails else "[FAIL]"
    print(f"{head} {os.path.basename(task_dir)}  "
          f"文件数={n_files}→{file_level}  产物数={n_outputs}  声明={declared}")
    for f in fails:
        print("        - " + f)
    for n in notes:
        print("        NOTE: " + n)
    print("        NOTE: Requirement 近似=判据条数/工具种类数=tool_set 长度；"
          "evidence-hop 仍须人工核对")
    return 1 if fails else 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        raise SystemExit(__doc__)
    rc = 0
    for d in args:
        rc |= check(d)
    print(f"\nFAIL 合计: {rc}")
    sys.exit(rc)
