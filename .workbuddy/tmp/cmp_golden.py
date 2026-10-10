# -*- coding: utf-8 -*-
"""比较容器复算产物与当前金标（md 与 5 张 PNG）的哈希。"""
import hashlib
import pathlib
import sys

GOLD = pathlib.Path(sys.argv[1])
GEN = pathlib.Path(sys.argv[2])


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


names = sorted([p.name for p in (GOLD / "FIN3-WKN-150_charts").iterdir()])
print("== 备忘録 ==")
m1 = GOLD / "FIN3-WKN-150_PreIPO投资决策备忘录.md"
m2 = GEN / "FIN3-WKN-150_PreIPO投资决策备忘录.md"
print("golden   ", sha(m1)[:16])
print("generated", sha(m2)[:16], "SAME" if sha(m1) == sha(m2) else "DIFF")
print("== 图表 ==")
for n in names:
    a = GOLD / "FIN3-WKN-150_charts" / n
    b = GEN / "FIN3-WKN-150_charts" / n
    ha, hb = sha(a)[:16], sha(b)[:16]
    print(f"{n[:46]:48} {'SAME' if ha == hb else 'DIFF'} {ha} {hb}")
