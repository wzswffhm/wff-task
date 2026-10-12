# -*- coding: utf-8 -*-
"""打包 fix9 批次包（zip 根 = 批次目录），显式写入 Unix 权限位：
   目录 0o40755 / 普通文件 0o100644 / .sh 0o100755。
排除 __pycache__、*.pyc、.DS_Store、_prev。
"""
import collections
import pathlib
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8')
BATCH_NAME = 'work_fin-b01_20261011_fix9-149'
ROOT = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness')
SRC = ROOT / BATCH_NAME
OUT = ROOT / f'{BATCH_NAME}.zip'
EXCLUDE_DIRS = {'__pycache__', '_prev', '.git', '.pytest_cache'}


def mode_of(p: pathlib.Path) -> int:
    if p.is_dir():
        return 0o40755
    return 0o100755 if p.suffix == '.sh' else 0o100644


def main():
    if not SRC.is_dir():
        print(f'[ERR] 批次目录不存在: {SRC}')
        return 1
    dirs, files = [], []
    for p in sorted(SRC.rglob('*')):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.suffix == '.pyc' or p.name == '.DS_Store':
            continue
        rel = f'{BATCH_NAME}/' + p.relative_to(SRC).as_posix()
        (dirs if p.is_dir() else files).append((rel + ('/' if p.is_dir() else ''), p))
    dirs.sort(key=lambda e: e[0])
    files.sort(key=lambda e: e[0])

    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zi = zipfile.ZipInfo(f'{BATCH_NAME}/')
        zi.external_attr = (0o40755 << 16) | 0x10
        zi.compress_type = zipfile.ZIP_STORED
        zf.writestr(zi, b'')
        for arc, _ in dirs:
            if arc == f'{BATCH_NAME}/':
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
    print(f'{OUT.name}: {len(info)} 条目, {OUT.stat().st_size:,} B ({OUT.stat().st_size/1048576:.2f} MiB)')
    print(f'  权限位分布: {dict(modes)}')
    print(f'  目录条目: {sum(1 for i in info if i.filename.endswith("/"))}')
    print(f'  异常权限: {bad or "无"}')
    print(f'  顶层: {sorted({n.filename.split("/")[0] for n in info})}')
    names = [i.filename for i in info]
    for key, desc in [('交付文档.md', '交付文档'),
                      ('跑分产物与轨迹/summary.json', 'summary'),
                      ('tests/rubrics.toml', 'rubrics.toml'),
                      ('solution/golden_output/FIN3-WKN-149_reproduce.py', '金标脚本'),
                      ('跑分产物与轨迹/oracle/reward.json', 'oracle reward'),
                      ('跑分产物与轨迹/qwen3.8-max-0902/reward.json', 'qwen reward')]:
        print(f'  含 {desc}: {any(n.endswith(key) for n in names)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
