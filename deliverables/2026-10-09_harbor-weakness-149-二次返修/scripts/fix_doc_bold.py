# -*- coding: utf-8 -*-
"""修正交付文档内的 markdown 加粗嵌套（模板已有 ** 包裹，占位符值又带了 **）。"""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
DOC = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                   r'\work_fin-b01_20261009_fix8-149\FIN3-WKN-149\交付文档.md')
FIXES = [
    ('| — | — | — | ****PASS**（< 0.70）** |',
     '| — | — | — | **PASS（< 0.70）** |'),
    ('结论：**三模型均分 **0.681373 < 0.70**，门禁 **PASS**；',
     '结论：**三模型均分 0.681373 < 0.70，门禁 PASS；'),
    ('`criteria_counted` 均为 **36**、`verifier_error` 均为 **0**。',
     '`criteria_counted` 均为 36、`verifier_error` 均为 0。'),
]

raw = DOC.read_bytes()
t = raw.decode('utf-8')
ok = True
for a, b in FIXES:
    c = t.count(a)
    print(('[OK]   ' if c == 1 else '[WARN] ') + f'{c} 处: {a[:56]}...')
    if c != 1:
        ok = False
    t = t.replace(a, b)
DOC.write_bytes(t.encode('utf-8'))
print(f'[OK] 四连星残留: {t.count("****")}   文档大小: {len(t.encode("utf-8")):,} B')
for ln in t.splitlines():
    if ln.startswith('结论：') or '三模型均分** |' in ln:
        print('    ', ln[:150])
print('结论修正闭环' if ok else '仍有未命中项')
