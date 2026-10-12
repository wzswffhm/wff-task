# -*- coding: utf-8 -*-
"""建立 fix10 批次目录（自 fix9 复制），并按质检报告(3) 项6 把 交付文档.md 移至批次根。
同时重写文档中与目录层级、批次名相关的表述，并新增 fix10 整改段。
"""
import shutil
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
H = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness')
SRC = H / 'work_fin-b01_20261011_fix9-149'
DST = H / 'work_fin-b01_20261011_fix10-149'
OLD_NAME = 'work_fin-b01_20261011_fix9-149'
NEW_NAME = 'work_fin-b01_20261011_fix10-149'

if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)
print(f'[OK] 批次目录已建立: {DST.name}')

# 交付文档移位到批次根
doc_old = DST / 'FIN3-WKN-149' / '交付文档.md'
doc_new = DST / '交付文档.md'
shutil.move(str(doc_old), str(doc_new))
print(f'[OK] 交付文档已移至批次根: {doc_new.relative_to(H)}')

t = doc_new.read_bytes().decode('utf-8')
NL = '\r\n' if '\r\n' in t else '\n'

fix = []
# 1) 批次名（跳过 §7/§8 历史轮引用行）
lines = t.split(NL)
HIST_MARKS = ['批次包结构改为', 'work_fin-b01_20261009_fix8-149/FIN3-WKN-149/{五件套',
              '本轮（fix8）', '该轮（fix8）']
n_ren = 0
for i, ln in enumerate(lines):
    if OLD_NAME in ln:
        # §8 历史段里描述 fix9 轮的批次名保留；仅当前状态引用改写
        if '本轮（fix9）' in ln or 'fix9 轮' in ln:
            continue
        lines[i] = ln.replace(OLD_NAME, NEW_NAME)
        n_ren += 1
t = NL.join(lines)
print(f'[OK] 批次名替换 {n_ren} 行')

fix.append((
    f'| 批次代号 | `{NEW_NAME}`（FIN3-WKN-149 对照 **2026-10-09 质检报告** + **2026-10-11 质检报告(2)** 三轮返修后的重交批次；本轮为 **fix9 金标三处计算修正轮**） |',
    f'| 批次代号 | `{NEW_NAME}`（FIN3-WKN-149 四次返修后的重交批次：10-09 报告 → fix8；10-11 报告(2) → fix9 金标三处修正；10-11 报告(3) → **fix10 Oracle 同源产物补跑 + 根交付说明移位**） |'))
fix.append((
    f'| 批次根目录 | `{NEW_NAME}/`（zip 根即批次目录）；`交付文档.md` 与 `跑分产物与轨迹/` **均归档于题目目录 `FIN3-WKN-149/` 内**，与五件套同级 |',
    f'| 批次根目录 | `{NEW_NAME}/`（zip 根即批次目录）；`交付文档.md` **位于批次根**（依质检报告(3) 项6 / rewardkit §8.4），`跑分产物与轨迹/` 归档于题目目录 `FIN3-WKN-149/` 内 |'))

for old, new in fix:
    c = t.count(old)
    print(f'  {"OK " if c == 1 else "WARN"} {c} 处: {old[:44]}...')
    t = t.replace(old, new, 1)

doc_new.write_bytes(t.encode('utf-8'))
print(f'[OK] 文档 {len(t.encode("utf-8")):,} B（批次名残留 {t.count(OLD_NAME)} 处应为历史段）')
