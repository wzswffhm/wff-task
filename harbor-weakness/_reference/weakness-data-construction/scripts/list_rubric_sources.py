#!/usr/bin/env python3
"""列出题包里全部 Implicit 判据，供逐条核对「判据要求是否有题面/材料依据」。

用法: python list_rubric_sources.py <task-dir> [...]

背景：甲方人检要求判据只能来自 ①题面显式要求 ②参考文件明确要求 ③可合理推导的隐含要求，
不允许存在凭空创造的伪需求。Explicit 条目题面已逐字写明；Implicit 条目需要逐条确认可推导，
本脚本把它们连同「题面中是否出现其数值/引号短语锚点」一起列出，便于人工判定。

判定提示：
  - 数值锚点未在题面出现是正常的——具体数值来自 environment/input_files/，题面本不该写。
  - 真正要查的是「要求本身」：题面有没有要求做这件事（或能否从任务目标合理推导）。
"""
import json
import os
import re
import sys

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
QUOTED = re.compile(r"「([^」]{2,30})」|`([^`]{2,40})`")


def anchors(text):
    nums = {n for n in NUM.findall(text) if len(n) >= 2}
    quoted = {a or b for a, b in QUOTED.findall(text)}
    return nums, quoted


def check(task_dir):
    task_dir = task_dir.rstrip("/\\")
    ins_path = os.path.join(task_dir, "instruction.md")
    rub_path = os.path.join(task_dir, "rubrics.json")
    if not (os.path.isfile(ins_path) and os.path.isfile(rub_path)):
        print(f"[SKIP] {task_dir}: 缺 instruction.md 或 rubrics.json")
        return 0
    ins = open(ins_path, encoding="utf-8").read()
    raw = json.load(open(rub_path, encoding="utf-8"))
    items = raw["items"] if isinstance(raw, dict) else raw
    imp = [i for i in items if i.get("criterion_necessity") == "Implicit"]
    print(f"===== {os.path.basename(task_dir)}  判据 {len(items)} 条，其中 Implicit {len(imp)} 条待逐条核")
    for it in imp:
        nums, quoted = anchors(it["description"])
        miss_q = [q for q in quoted if q not in ins]
        miss_n = [n for n in nums if n not in ins and n.replace(",", "") not in ins]
        flags = []
        if miss_q:
            flags.append("题面未出现引号短语:" + "、".join(sorted(miss_q)[:3]))
        if miss_n:
            flags.append(f"题面未出现数值 {len(miss_n)} 个")
        print(f"  [{it['id']}] {it['dimension']} w={it['weight']} {it['type']}")
        print(f"      要求: {it['description'][:150]}")
        print(f"      提示: {'; '.join(flags) if flags else '题面锚点全部命中'}")
        print("      需人工确认: 该「要求」是否题面明文 / 材料明确 / 可由任务目标合理推导")
    print()
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        raise SystemExit(__doc__)
    rc = 0
    for d in args:
        rc |= check(d)
    sys.exit(rc)
