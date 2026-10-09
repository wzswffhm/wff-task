# -*- coding: utf-8 -*-
"""FIN3-WKN-150 第二轮质检整改：提升 [task].version 1.0.3 -> 1.0.4。

同步：题包本体 + 两个批次内副本。用 Python 读写（PowerShell 5.1 会把含中文的
task.toml 按 ANSI 解码，写回即损坏）。
"""
import pathlib

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TARGETS = [
    REPO / "harbor-weakness/FIN3-WKN-150/task.toml",
    REPO / "harbor-weakness/work-金融-私募股权投资-20261008/FIN3-WKN-150/task.toml",
    REPO / "harbor-weakness/work_fin-b01_20261006_fix3-150/FIN3-WKN-150/task.toml",
]
OLD, NEW = 'version = "1.0.3"', 'version = "1.0.4"'

for p in TARGETS:
    if not p.is_file():
        print(f"[缺失] {p}")
        continue
    text = p.read_text(encoding="utf-8")
    n = text.count(OLD)
    if n == 0:
        print(f"[跳过] {p.relative_to(REPO)}（无 {OLD}）")
        continue
    p.write_text(text.replace(OLD, NEW), encoding="utf-8", newline="\n")
    print(f"[OK]   {p.relative_to(REPO)}  替换 {n} 处 -> 1.0.4")
