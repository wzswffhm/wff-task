# -*- coding: utf-8 -*-
"""把批次目录重命名为 fix9 轮次名（work_fin-b01_20261011_fix9-149）。"""
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')
H = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness')
OLD = H / 'work_fin-b01_20261009_fix8-149'
NEW = H / 'work_fin-b01_20261011_fix9-149'

print(f'源存在={OLD.is_dir()}  目标已存在={NEW.exists()}')
if not OLD.is_dir():
    print('[ERR] 源批次目录不存在')
    sys.exit(1)
if NEW.exists():
    print('[INFO] 目标已存在，先删除')
    shutil.rmtree(NEW)
shutil.move(str(OLD), str(NEW))
print(f'[OK] 已重命名 -> {NEW.name}')

# 校验结构
for sub in ['FIN3-WKN-149', 'FIN3-WKN-149/交付文档.md', 'FIN3-WKN-149/跑分产物与轨迹/summary.json',
            'FIN3-WKN-149/tests/rubrics.toml', 'FIN3-WKN-149/solution/golden_output']:
    p = NEW / sub
    print(f'  {"OK " if p.exists() else "MISS"} {sub}')
n_files = sum(1 for _ in NEW.rglob('*') if _.is_file())
print(f'  文件总数 {n_files}')
