# -*- coding: utf-8 -*-
"""fix11 飞书回写：三附件全部更新为 Unix 权限语义版本（交付物换 fix11 包）。
用法: python feishu_writeback_fix11.py [--apply]
"""
import json
import os
import pathlib
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8')
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT, TB, REC = "QpzNb4fXSamfX6sLloBcPfHNnug", "tblPNrBtjFfwOowN", "rec28himvkSA77"
H = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness')
NEW = 'work_fin-b01_20261011_fix11-149'
TARGETS = [
    ('题目附件信息', 'fldf8Ymaw2', H / 'FIN3-WKN-149_task.zip', 'same-name'),
    ('标准答案附件信息', 'fld2TmGhqt', H / 'FIN3-WKN-149_answer.zip', 'same-name'),
    ('交付物', 'fld8TMUhqI', H / f'{NEW}.zip', 'all'),
]
APPLY = '--apply' in sys.argv
env = dict(os.environ)
env["LARK_CLI_NO_PROXY"] = "1"


def lark(*args, yes=False):
    cmd = [LARK] + list(args)
    if yes:
        cmd.append('--yes')
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=env)
    return p.returncode, (p.stdout or ''), (p.stderr or '')


def read_row():
    rc, out, err = lark('base', '+record-list', '--base-token', BT, '--table-id', TB,
                        '--page-size', '100', '--as', 'user', '--format', 'json')
    dd = json.loads(out)['data']
    idx = {n: i for i, n in enumerate(dd['fields'])}
    return dd, idx, dd['data'][dd['record_id_list'].index(REC)]


def atts_of(dd, idx, row, fname):
    v = row[idx[fname]]
    return v if isinstance(v, list) else []


print(f'模式: {"APPLY" if APPLY else "DRY-RUN"}\n')
for name, fid, f, mode in TARGETS:
    z = zipfile.ZipFile(f)
    cs = {i.create_system for i in z.infolist()}
    print(f'  {f.name}: {f.stat().st_size:,} B  create_system集合={cs}  '
          f'条目={len(z.infolist())}')

dd, idx, row = read_row()
print('\n=== 上传前 ===')
for fname, fid, f, mode in TARGETS:
    a = atts_of(dd, idx, row, fname)
    print(f'  [{fname}] 附件数={len(a)}')
    for x in a:
        print(f'     - {x.get("name")}  {x.get("size")}B')

if not APPLY:
    print('\n（DRY-RUN；加 --apply 执行）')
    sys.exit(0)

for fname, fid, f, mode in TARGETS:
    dd, idx, row = read_row()
    for x in atts_of(dd, idx, row, fname):
        if mode == 'same-name' and x.get('name') != f.name:
            print(f'  [跳过] {fname} 保留 {x.get("name")}')
            continue
        rc, out, err = lark('base', '+record-remove-attachment', '--base-token', BT,
                            '--table-id', TB, '--record-id', REC, '--field-id', fid,
                            '--file-token', x['file_token'], '--as', 'user',
                            '--format', 'json', yes=True)
        print(f'  [删除] {fname} {x.get("name")}({x.get("size")}B) rc={rc}')
    rc, out, err = lark('base', '+record-upload-attachment', '--base-token', BT,
                        '--table-id', TB, '--record-id', REC, '--field-id', fid,
                        '--file', str(f), '--as', 'user', '--format', 'json')
    print(f'  [上传] {fname} {f.name} rc={rc}  {(out or err)[:100]}')

dd, idx, row = read_row()
print('\n=== 上传后 ===')
ok = True
for fname, fid, f, mode in TARGETS:
    a = atts_of(dd, idx, row, fname)
    hit = any(x.get('size') == f.stat().st_size for x in a)
    ok &= hit and len(a) == 1
    print(f'  [{fname}] 附件数={len(a)}  {"✅" if hit else "⚠"}')
    for x in a:
        print(f'     - {x.get("name")}  {x.get("size")}B  '
              f'{"本次新包" if x.get("size") == f.stat().st_size else "其他"}')
print('\n结论:', '三附件终态正确 ✅' if ok else '存在未达预期 ⚠')
sys.exit(0 if ok else 2)
