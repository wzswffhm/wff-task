# -*- coding: utf-8 -*-
"""§7 标题与首句改为历史轮（fix8），避免「本轮」歧义（fix9 才是本轮）。"""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
DOC = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                   r'\work_fin-b01_20261009_fix8-149\FIN3-WKN-149\交付文档.md')
t = DOC.read_bytes().decode('utf-8')
NL = '\r\n' if '\r\n' in t else '\n'

fix = [
    ('## 7. 本轮（2026-10-09 二次返修）整改记录',
     '## 7. 前轮（2026-10-09 二次返修，fix8）整改记录'),
    ('甲方于 2026-10-09 出具质检报告（结论：待返修），本轮按报告**逐项闭环**，并按"输入规则修订须重新生成候选 job"要求**全量重跑四执行体**。',
     '甲方于 2026-10-09 出具质检报告（结论：待返修），该轮（fix8）按报告**逐项闭环**，并按"输入规则修订须重新生成候选 job"要求**全量重跑四执行体**。（本轮 fix9 的整改记录见 §8。）'),
    ('### 7.1 附带整改', '### 7.1 该轮附带整改'),
    # §6 里 fix8 也叫过「本轮」—— 6.2 若有则处理
    ('### 6.2 对照 10-08 质检报告（fix7 轮）', '### 6.2 对照 10-08 质检报告（fix7 轮）'),
]
ok = 0
for old, new in fix:
    c = t.count(old)
    if c == 1:
        t = t.replace(old, new, 1)
        ok += 1
    else:
        print(f'  [WARN] {c}: {old[:40]}')

# §6.1 标题若叫「本轮」也修
if '### 6.1 对照 10-05 复检质检问题清单（fix7 轮）' in t:
    ok += 0

DOC.write_bytes(t.encode('utf-8'))
print(f'[OK] 修正 {ok}/{len(fix)}；文档 {len(t.encode("utf-8")):,} B')
