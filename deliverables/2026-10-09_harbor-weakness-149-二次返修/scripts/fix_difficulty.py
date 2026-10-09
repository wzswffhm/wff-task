# -*- coding: utf-8 -*-
"""按 2026-10-09 二次返修实测均分（0.681373）重新定档：A2 -> A1。
三处同步：keywords / metadata.difficulty / tags。
用 bytes 读写以保持原行尾（CRLF/LF）不变。
"""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
TARGETS = [
    pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149\task.toml'),
    pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                 r'\work_fin-b01_20261009_fix8-149\FIN3-WKN-149\task.toml'),
]
REPL = [
    ('keywords = ["finance", "office", "A2"]', 'keywords = ["finance", "office", "A1"]'),
    ('difficulty = "A2"', 'difficulty = "A1"'),
    ('tags = ["finance", "office", "A2", "weakness"', 'tags = ["finance", "office", "A1", "weakness"'),
]

for p in TARGETS:
    raw = p.read_bytes()
    t = raw.decode('utf-8')
    crlf = '\r\n' in t
    n = 0
    for a, b in REPL:
        c = t.count(a)
        if c != 1:
            print(f'  [WARN] {p.parent.name}: 期望 1 处 "{a[:38]}..."，实际 {c} 处')
        t = t.replace(a, b)
        n += c
    p.write_bytes(t.encode('utf-8'))
    left = sum(t.count(x) for x in ['"A2"'])
    print(f'[OK] {p.parent.name}/task.toml  替换 {n} 处  行尾={"CRLF" if crlf else "LF"}  '
          f'剩余 "A2" 出现 {left} 次')
    for ln in t.splitlines():
        if 'difficulty' in ln or 'keywords' in ln or ln.startswith('tags'):
            print('     ', ln)
