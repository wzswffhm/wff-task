# -*- coding: utf-8 -*-
"""§9（fix10 前轮记录）内的批次名还原为当时的 fix10 名，避免历史记录失真。"""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
DOC = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                   r'\work_fin-b01_20261011_fix11-149\交付文档.md')
t = DOC.read_bytes().decode('utf-8')

FIX = [
    # §9 项6 闭环证据
    ('① 批次包结构：`work_fin-b01_20261011_fix11-149/交付文档.md`（根）+ '
     '`work_fin-b01_20261011_fix11-149/FIN3-WKN-149/{五件套, 跑分产物与轨迹/}`；',
     '① 批次包结构：`<批次根>/交付文档.md`（根）+ `<批次根>/FIN3-WKN-149/{五件套, 跑分产物与轨迹/}`'
     '（该轮批次名 `work_fin-b01_20261011_fix10-149`）；'),
    # §9.1 结构图
    ('work_fin-b01_20261011_fix11-149/                       ← 批次目录（zip 根）',
     'work_fin-b01_20261011_fix10-149/                       ← 批次目录（zip 根，该轮名）'),
]
ok = 0
for old, new in FIX:
    c = t.count(old)
    print(f'  {"OK " if c == 1 else "WARN"} {c} 处: {old[:50]}...')
    if c == 1:
        ok += 1
    t = t.replace(old, new, 1)
DOC.write_bytes(t.encode('utf-8'))
print(f'\n[OK] 修正 {ok}/{len(FIX)}  文档 {len(t.encode("utf-8")):,} B')
print(f'[检查] fix10 名出现 {t.count("work_fin-b01_20261011_fix10-149")} 次（历史段），'
      f'fix11 名出现 {t.count("work_fin-b01_20261011_fix11-149")} 次（当前）')
