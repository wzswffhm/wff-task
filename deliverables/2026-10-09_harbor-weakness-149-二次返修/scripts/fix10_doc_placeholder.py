# -*- coding: utf-8 -*-
"""修正 §9 中残留的 oracle 试次号占位符。"""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
DOC = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                   r'\work_fin-b01_20261011_fix10-149\交付文档.md')
TRIAL = 'FIN3-WKN-149__YbBiCYB'
t = DOC.read_bytes().decode('utf-8')
old = "FIN3-WKN-149__('__PLACEHOLDER__')"
c = t.count(old)
print(f'命中 {c} 处: {old}')
t = t.replace(old, TRIAL)
DOC.write_bytes(t.encode('utf-8'))
print(f'[OK] 残留 PLACEHOLDER: {t.count("PLACEHOLDER")}  文档 {len(t.encode("utf-8")):,} B')
print(f'[OK] 试次号出现 {t.count(TRIAL)} 次')
