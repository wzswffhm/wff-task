# -*- coding: utf-8 -*-
"""探测 sources-*.html 的锚点元素结构（只看前若干 KB 的正文部分）。"""
import io, re, sys, os

SRC = r"C:\Users\Administrator\Desktop\Windows-48题质检-专家修复详解版-20261012\evidence"
key = sys.argv[1] if len(sys.argv) > 1 else "019"
p = os.path.join(SRC, f"sources-{key}.html")
with io.open(p, "r", encoding="utf-8") as f:
    html = f.read()

print("len =", len(html))
# 找 toc 结束后的第一个锚点元素
m = re.search(r'</details>', html)
print("first </details> at", m.start() if m else None)
seg = html[m.start(): m.start() + 3000] if m else html[:3000]
print(seg)
