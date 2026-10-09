# -*- coding: utf-8 -*-
"""FIN3-WKN-150 第三轮（fix5）：同步判据到批次副本 + 版本 1.0.4 -> 1.0.5。

1) 题包本体的 tests/rubrics.toml、rubrics.json 复制到批次副本（R29/R30 收紧）
2) [task].version 1.0.4 -> 1.0.5（题包本体 + 2 个批次副本，与上轮 bump_version.py 同口径）
3) summary.json 的 task_version -> 1.0.5（原为 1.0.3，fix4 未同步，本轮一并对齐）
"""
import json
import pathlib
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
H = REPO / "harbor-weakness"
SRC = H / "FIN3-WKN-150"                       # 题包本体（判据已收紧）
DST = H / "work-金融-私募股权投资-20261008" / "FIN3-WKN-150"   # 打包源
REL = ["tests/rubrics.toml", "rubrics.json"]

OLD_V, NEW_V = 'version = "1.0.4"', 'version = "1.0.5"'
TASK_TOMLS = [
    H / "FIN3-WKN-150" / "task.toml",
    H / "work-金融-私募股权投资-20261008" / "FIN3-WKN-150" / "task.toml",
    H / "work_fin-b01_20261006_fix3-150" / "FIN3-WKN-150" / "task.toml",
]
SUMMARY = DST / "跑分产物与轨迹" / "summary.json"

DRY = "--dry-run" in sys.argv


def main():
    # 1) 同步判据
    print("== 1. 同步判据到批次副本 ==")
    for rel in REL:
        a, b = SRC / rel, DST / rel
        if not a.is_file() or not b.is_file():
            print(f"  [缺] {rel}")
            return 1
        same = a.read_bytes() == b.read_bytes()
        print(f"  {rel}: 已一致={same}" + ("" if same else " -> 复制"))
        if not same and not DRY:
            shutil.copy2(a, b)

    # 2) bump version
    print("\n== 2. [task].version 1.0.4 -> 1.0.5 ==")
    for p in TASK_TOMLS:
        if not p.is_file():
            print(f"  [缺失] {p}")
            continue
        t = p.read_text(encoding="utf-8")
        n = t.count(OLD_V)
        if n == 0:
            m = re.search(r'^version = "([^"]+)"', t, re.M)
            print(f"  [跳过] {p.relative_to(REPO)}（当前 {m.group(1) if m else '?'}）")
            continue
        if not DRY:
            p.write_text(t.replace(OLD_V, NEW_V), encoding="utf-8", newline="\n")
        print(f"  [OK] {p.relative_to(REPO)}  替换 {n} 处")

    # 3) summary.json task_version
    print("\n== 3. summary.json 的 task_version 对齐 ==")
    if SUMMARY.is_file():
        s = json.loads(SUMMARY.read_text(encoding="utf-8"))
        old = s.get("task_version")
        print(f"  task_version: {old} -> 1.0.5")
        if not DRY:
            s["task_version"] = "1.0.5"
            SUMMARY.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

    # 复检
    print("\n== 复检 ==")
    ok = True
    for rel in REL:
        same = (SRC / rel).read_bytes() == (DST / rel).read_bytes()
        ok &= same
        print(f"  {rel} 本体==批次: {same}")
    for p in TASK_TOMLS:
        if p.is_file():
            m = re.search(r'^version = "([^"]+)"', p.read_text(encoding="utf-8"), re.M)
            print(f"  {p.relative_to(REPO)}: {m.group(1)}")
    if SUMMARY.is_file():
        s = json.loads(SUMMARY.read_text(encoding="utf-8"))
        print(f"  summary task_version: {s.get('task_version')}  mean: {s.get('mean')}  gate_pass: {s.get('gate_pass')}")
    print("\n>>> " + ("完成" if ok else "!! 仍有不一致"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
