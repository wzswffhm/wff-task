# -*- coding: utf-8 -*-
"""批量替换 wchunk-216 题包里可机械改写的身份/路径引用（wfmt-215 -> wchunk-216）。

只处理「注释、路径、包名、文件名、任务身份」这类机械替换；
需要语义重写的文件（instruction.md / rubric.json / 两个 README / hidden 旧套件）
不在本脚本范围内，它们会另行重写或落盘。

替换顺序刻意按「长串优先」，避免 sample.wfmt 被 wfmt->wchunk 规则误伤成 sample.wchunk。
"""
import pathlib
import sys

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wchunk-216")

# 语义重写文件：本脚本跳过
SKIP = {
    "instruction.md",
    "rubric.json",
    "README.md",              # workspace/README.md 与 solution/README.md 都会重写
    "test_wfmt_semantics.py",  # 旧 hidden 套件，直接删
}

# (old, new) —— 长串优先
RULES = [
    ("sample_empty.wfmt", "sample_empty.wchk"),
    ("sample.wfmt", "sample.wchk"),
    ("wfflab__wfmt-215", "wfflab__wchunk-216"),
    ("wfflab/wfmt-215", "wfflab/wchunk-216"),
    ("wfmt-215", "wchunk-216"),
    ("test_wfmt_basic.py", "test_wchunk_basic.py"),
    ("test_wfmt_semantics.py", "test_wchunk_semantics.py"),
    ("WFormatError", "WChunkError"),
    ("wfmt", "wchunk"),
    ("Wfmt", "Wchunk"),
]

# 这些文件里才允许改协议版本 2.0.0 -> 1.0.0
VERSION_FILES = {"task.toml", "test.ps1", "aggregate_results.ps1", "judge.toml", "adapter.toml"}

changed = 0
scanned = 0
for path in sorted(TASK.rglob("*")):
    if not path.is_file():
        continue
    if path.name in SKIP:
        continue
    if path.suffix.lower() not in {".ps1", ".bat", ".toml", ".json", ".py", ".md"}:
        continue
    if "jobs" in path.relative_to(TASK).parts:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    scanned += 1
    original = text
    for old, new in RULES:
        if old in text:
            text = text.replace(old, new)
    if path.name in VERSION_FILES and "2.0.0" in text:
        text = text.replace("2.0.0", "1.0.0")
    if text != original:
        path.write_text(text, encoding="utf-8", newline="\n")
        changed += 1
        print(f"  [OK] {path.relative_to(TASK)}")

print(f"\n扫描 {scanned} 个文件，改写 {changed} 个")

# 复查：排除跳过的文件后不应再有 wfmt
leftovers = []
for path in TASK.rglob("*"):
    if not path.is_file() or path.suffix.lower() not in {".ps1", ".bat", ".toml", ".json", ".py", ".md"}:
        continue
    if "jobs" in path.relative_to(TASK).parts:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    if "wfmt" in text or "WFormatError" in text or "WFMT" in text:
        leftovers.append(str(path.relative_to(TASK)))

if leftovers:
    print("\n仍含 wfmt 的文件（应只剩待重写的 4 类 + hidden 旧套件）：")
    for item in leftovers:
        print(f"  - {item}")
else:
    print("\n无 wfmt 残留")
