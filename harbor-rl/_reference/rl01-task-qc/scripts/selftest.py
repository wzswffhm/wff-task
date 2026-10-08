#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用「已知良好的题包 + 注入缺陷」回归 check_task_qc.py，防止某个检查静默失效。

用法:
    python selftest.py <已知良好的 task-dir>

做法：把题包复制到临时目录，逐项注入缺陷，每次只跑一次检查，断言对应问题码被报出来，
最后清理临时目录。若某个断言没命中，说明该检查坏了或与题包形态脱节。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def mutate(task_dir, kind):
    """按类型注入一个缺陷，返回期望命中的检查码。"""
    if kind == "dup_deliverables":
        p = os.path.join(task_dir, "tests", "rubrics.toml")
        t = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8", newline="").write(
            t.replace("Deliverables to inspect: ",
                      "Deliverables to inspect: ``. Deliverables to inspect: ", 1))
        return "Q-T05"
    if kind == "drop_hard_constraint":
        p = os.path.join(task_dir, "instruction.md")
        t = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8", newline="").write(
            re.sub(r"(?ms)^#+\s*硬约束.*?(?=^#|\Z)", "", t))
        return "Q-T02"
    if kind == "leak_rubric_id":
        p = os.path.join(task_dir, "instruction.md")
        t = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8", newline="").write(t + "\n\nR07 满足即得满分。\n")
        return "Q-T03"
    if kind == "lose_golden_file":
        g = os.path.join(task_dir, "solution", "golden_output")
        for f in sorted(os.listdir(g)):
            if os.path.isfile(os.path.join(g, f)):
                os.remove(os.path.join(g, f))
                return "Q-T04"
        raise RuntimeError("golden_output 为空，无法注入")
    if kind == "judge_in_environment":
        p = os.path.join(task_dir, "task.toml")
        t = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8", newline="").write(
            t + '\n[environment.env]\nJUDGE_API_KEY = "leaked"\n')
        return "Q-T08"
    if kind == "dup_part_head":
        # 把第一个「第X部分：」标题整行复制一遍 → 与声明的部分数不符
        p = os.path.join(task_dir, "instruction.md")
        t = open(p, encoding="utf-8").read()
        m = re.search(r"(?m)^\*\*第[一二三四五六七八九十]+部分[：:][^\n]*$", t)
        if not m:
            # 本地增量（2026-10-02）：题面用「1. **…**」编号列表枚举部分时没有「第X部分」标题，
            #   改用复制编号条目来制造「声明数与条目数不符」，Q-T10 的编号列表分支应能捕获。
            m = re.search(r"(?m)^\s*\d+\s*[.、]\s*\*\*[^\n]*$", t)
        if not m:
            raise RuntimeError("题面既没有「**第X部分：」标题，也没有「1. **…**」编号条目，无法注入")
        open(p, "w", encoding="utf-8", newline="").write(
            t[:m.end()] + "\n\n" + m.group(0) + "\n" + t[m.end():])
        return "Q-T10"
    raise ValueError(kind)


def repair(task_dir, kind):
    """反向用例：把基准包里已存在的某个缺陷消除，断言对应检查码消失。"""
    if kind == "fix_part_decl":
        # 删掉「第X部分之后增加一段」那类编外段，Q-T10 应随之消失
        p = os.path.join(task_dir, "instruction.md")
        t = open(p, encoding="utf-8").read()
        new = re.sub(r"(?m)^.*第[一二三四五六七八九十]+部分[^。\n]{0,10}"
                     r"(?:之后|后)\s*(?:增加|插入|补充).*\n?", "", t)
        if new == t:
            return None
        open(p, "w", encoding="utf-8", newline="").write(new)
        return "Q-T10"
    raise ValueError(kind)


KINDS = ["dup_deliverables", "drop_hard_constraint", "leak_rubric_id",
         "lose_golden_file", "judge_in_environment", "dup_part_head"]
REVERSE_KINDS = ["fix_part_decl"]


def run_codes(task):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "check_task_qc.py"), task, "--json"],
        capture_output=True, env=env)
    data = json.loads(proc.stdout.decode("utf-8", "replace"))
    return {r["code"] for r in data["results"]}


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    good = os.path.abspath(sys.argv[1]).rstrip("\\/")
    ok = True
    for kind in KINDS:
        tmp = tempfile.mkdtemp(prefix="qc-selftest-")
        task = os.path.join(tmp, "T")
        try:
            shutil.copytree(good, task)
            expect = mutate(task, kind)
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
            proc = subprocess.run(
                [sys.executable, os.path.join(HERE, "check_task_qc.py"), task, "--json"],
                capture_output=True, env=env)
            data = json.loads(proc.stdout.decode("utf-8", "replace"))
            codes = {r["code"] for r in data["results"]}
            hit = expect in codes
            ok = ok and hit
            print(f"{'PASS' if hit else 'FAIL'}  {kind:<24} 期望 {expect}  "
                  f"实际命中 {sorted(codes) or '无'}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("\n自检结论：", "全部通过" if ok else "有检查未触发，需修 check_task_qc.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
