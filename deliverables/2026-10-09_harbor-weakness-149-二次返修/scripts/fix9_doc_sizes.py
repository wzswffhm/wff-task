# -*- coding: utf-8 -*-
"""§9 补 task/answer 精确大小（非自指），随后重打包批次包。"""
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
H = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness')
BATCH = H / 'work_fin-b01_20261011_fix9-149'
DOC = BATCH / 'FIN3-WKN-149' / '交付文档.md'
TASK_ZIP = H / 'FIN3-WKN-149_task.zip'
ANS_ZIP = H / 'FIN3-WKN-149_answer.zip'
PY = r'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'

t = DOC.read_bytes().decode('utf-8')
fix = [
    ('| 题目附件 `fldf8Ymaw2` | attachment | 同名前删后传 | `FIN3-WKN-149_task.zip`（含修正后 `reproduce.py`、重建金标与 `[scoring]` 判据） |',
     f'| 题目附件 `fldf8Ymaw2` | attachment | 同名前删后传 | `FIN3-WKN-149_task.zip`（**{TASK_ZIP.stat().st_size:,} B**，含修正后 `reproduce.py`、重建金标与 `[scoring]` 判据） |'),
    ('| 标准答案附件 `fld2TmGhqt` | attachment | 同名前删后传 | `FIN3-WKN-149_answer.zip`（含重建后金标 7 件套） |',
     f'| 标准答案附件 `fld2TmGhqt` | attachment | 同名前删后传 | `FIN3-WKN-149_answer.zip`（**{ANS_ZIP.stat().st_size:,} B**，含重建后金标 7 件套） |'),
]
for old, new in fix:
    c = t.count(old)
    print(f'  {"OK " if c == 1 else "WARN"} {c} 处: {old[:50]}...')
    t = t.replace(old, new, 1)
DOC.write_bytes(t.encode('utf-8'))
print(f'[OK] 文档 {len(t.encode("utf-8")):,} B')

print('\n=== 重打包 ===')
r = subprocess.run([PY, str(pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                                         r'\2026-10-09_harbor-weakness-149-二次返修\scripts\pack_batch_fix9.py'))],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
print(r.stdout[-700:])
print(r.stderr[-300:] if r.stderr else '')
