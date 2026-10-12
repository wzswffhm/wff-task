# -*- coding: utf-8 -*-
"""打包指定批次目录为 zip（zip 根 = 批次目录），显式写入 Unix 权限位。
用法: python pack_batch_generic.py work_fin-b01_20261011_fix10-149
"""
import collections
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8')
NAME = sys.argv[1] if len(sys.argv) > 1 else 'work_fin-b01_20261011_fix10-149'
ROOT = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness')
SRC = ROOT / NAME
OUT = ROOT / f'{NAME}.zip'
EXCLUDE_DIRS = {'__pycache__', '_prev', '.git', '.pytest_cache'}


def mode_of(p: pathlib.Path) -> int:
    if p.is_dir():
        return 0o40755
    return 0o100755 if p.suffix == '.sh' else 0o100644


if not SRC.is_dir():
    print(f'[ERR] 批次目录不存在: {SRC}')
    sys.exit(1)
dirs, files = [], []
for p in sorted(SRC.rglob('*')):
    if any(part in EXCLUDE_DIRS for part in p.parts):
        continue
    if p.suffix == '.pyc' or p.name == '.DS_Store':
        continue
    rel = f'{NAME}/' + p.relative_to(SRC).as_posix()
    (dirs if p.is_dir() else files).append((rel + ('/' if p.is_dir() else ''), p))
dirs.sort(key=lambda e: e[0])
files.sort(key=lambda e: e[0])

if OUT.exists():
    OUT.unlink()
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    zi = zipfile.ZipInfo(f'{NAME}/')
    zi.external_attr = (0o40755 << 16) | 0x10
    zi.compress_type = zipfile.ZIP_STORED
    zf.writestr(zi, b'')
    for arc, _ in dirs:
        if arc == f'{NAME}/':
            continue
        zi = zipfile.ZipInfo(arc)
        zi.external_attr = (0o40755 << 16) | 0x10
        zi.compress_type = zipfile.ZIP_STORED
        zf.writestr(zi, b'')
    for arc, src in files:
        zi = zipfile.ZipInfo(arc)
        zi.external_attr = mode_of(src) << 16
        zi.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(zi, src.read_bytes())

info = zipfile.ZipFile(OUT).infolist()
modes = collections.Counter(oct(i.external_attr >> 16) for i in info)
bad = [i.filename for i in info
       if not i.filename.endswith('/') and (i.external_attr >> 16) not in (0o100644, 0o100755)]
names = [i.filename for i in info]
print(f'{OUT.name}: {len(info)} 条目, {OUT.stat().st_size:,} B ({OUT.stat().st_size/1048576:.2f} MiB)')
print(f'  权限位: {dict(modes)}   目录条目: {sum(1 for i in info if i.filename.endswith("/"))}')
print(f'  异常权限: {bad or "无"}')
print(f'  顶层: {sorted({n.split("/")[0] for n in names})}')
# 交付文档须在批次根
print(f'  交付文档在批次根: {any(n == f"{NAME}/交付文档.md" for n in names)}')
print(f'  题目目录有 跑分产物与轨迹: {any(n.startswith(f"{NAME}/FIN3-WKN-149/跑分产物与轨迹/") for n in names)}')
print(f'  含 oracle reward: {any(n.endswith("跑分产物与轨迹/oracle/reward.json") for n in names)}')
print(f'  含 summary: {any(n.endswith("跑分产物与轨迹/summary.json") for n in names)}')
