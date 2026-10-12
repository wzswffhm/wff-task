# -*- coding: utf-8 -*-
"""fix10 飞书回写：仅替换交付物字段为 fix10 批次包（旧 fix9 包删除，保证单一附件）。
task.zip / answer.zip 本轮内容未变，不重传。
用法: python feishu_writeback_fix10.py [--apply]
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
BATCH_ZIP = H / 'work_fin-b01_20261011_fix10-149.zip'
TASK_ZIP = H / 'FIN3-WKN-149_task.zip'
ANS_ZIP = H / 'FIN3-WKN-149_answer.zip'
F_DELIVER = 'fld8TMUhqI'
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


print(f'模式: {"APPLY" if APPLY else "DRY-RUN"}\n')
print(f'  待传 {BATCH_ZIP.name}: {BATCH_ZIP.stat().st_size:,} B')
print(f'  本轮不重传 task.zip({TASK_ZIP.stat().st_size:,} B) / answer.zip({ANS_ZIP.stat().st_size:,} B)（内容未变）')

bz = zipfile.ZipFile(BATCH_ZIP)
names = bz.namelist()
print(f'\n  包自检: {len(names)} 条目  交付文档在根='
      f'{any(n == "work_fin-b01_20261011_fix10-149/交付文档.md" for n in names)}')
rp = bz.read('work_fin-b01_20261011_fix10-149/FIN3-WKN-149/跑分产物与轨迹/oracle/reward.json'
             ).decode('utf-8')
print(f'  oracle reward in zip: {rp.strip()[:110]}')
sm = json.loads(bz.read('work_fin-b01_20261011_fix10-149/FIN3-WKN-149/'
                        '跑分产物与轨迹/summary.json').decode('utf-8'))
print(f'  summary: round={sm["round"][:50]}  mean={sm["model_mean"]:.6f}  gate={sm["gate_pass"]}')

dd, idx, row = read_row()
print(f'\n=== 上传前 交付物 ===')
for x in (row[idx['交付物']] or []):
    print(f'  - {x.get("name")}  {x.get("size")}B  token={x.get("file_token")}')

if not APPLY:
    print('\n（DRY-RUN；加 --apply 执行）')
    sys.exit(0)

dd, idx, row = read_row()
for x in (row[idx['交付物']] or []):
    rc, out, err = lark('base', '+record-remove-attachment', '--base-token', BT,
                        '--table-id', TB, '--record-id', REC, '--field-id', F_DELIVER,
                        '--file-token', x['file_token'], '--as', 'user', '--format', 'json', yes=True)
    print(f'  [删除] {x.get("name")}({x.get("size")}B) rc={rc}')

rc, out, err = lark('base', '+record-upload-attachment', '--base-token', BT, '--table-id', TB,
                    '--record-id', REC, '--field-id', F_DELIVER, '--file', str(BATCH_ZIP),
                    '--as', 'user', '--format', 'json')
print(f'  [上传] {BATCH_ZIP.name} rc={rc}  {(out or err)[:110]}')

dd, idx, row = read_row()
print('\n=== 上传后 ===')
ok = False
for x in (row[idx['交付物']] or []):
    hit = x.get('size') == BATCH_ZIP.stat().st_size
    ok |= hit
    print(f'  - {x.get("name")}  {x.get("size")}B  {"✅ 本次新包" if hit else "⚠ 其他"}')
print('\n结论:', '交付物终态正确 ✅' if ok else '未达预期 ⚠')
sys.exit(0 if ok else 2)
