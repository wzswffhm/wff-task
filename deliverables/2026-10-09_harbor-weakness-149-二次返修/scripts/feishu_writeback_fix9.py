# -*- coding: utf-8 -*-
"""fix9 飞书回写：
  题目附件信息   fldf8Ymaw2 <- FIN3-WKN-149_task.zip
  标准答案附件信息 fld2TmGhqt <- FIN3-WKN-149_answer.zip
  交付物        fld8TMUhqI <- work_fin-b01_20261011_fix9-149.zip（删旧 fix8 包，保证单一附件）

用法: python feishu_writeback_fix9.py [--apply]
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
TASK_ZIP = H / 'FIN3-WKN-149_task.zip'
ANS_ZIP = H / 'FIN3-WKN-149_answer.zip'
BATCH_ZIP = H / 'work_fin-b01_20261011_fix9-149.zip'
APPLY = '--apply' in sys.argv

TARGETS = [
    ('题目附件信息', 'fldf8Ymaw2', TASK_ZIP, 'same-name'),
    ('标准答案附件信息', 'fld2TmGhqt', ANS_ZIP, 'same-name'),
    ('交付物', 'fld8TMUhqI', BATCH_ZIP, 'all'),
]
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


def main():
    print(f'模式: {"APPLY（实际写入）" if APPLY else "DRY-RUN（只读）"}\n')
    for name, f in [('task', TASK_ZIP), ('answer', ANS_ZIP), ('batch', BATCH_ZIP)]:
        print(f'  待传 {f.name}: {f.stat().st_size:,} B  存在={f.is_file()}')

    # 包内自检
    tz = zipfile.ZipFile(TASK_ZIP)
    rl = tz.read('FIN3-WKN-149/tests/rubrics.toml').decode('utf-8')
    print(f'\n  task.zip 含 [scoring] aggregation = {"aggregation" in rl}  '
          f'判据数={rl.count("[[criterion]]")}')
    bz = zipfile.ZipFile(BATCH_ZIP)
    names = bz.namelist()
    print(f'  batch.zip: {len(names)} 条目  '
          f'含交付文档={any(n.endswith("FIN3-WKN-149/交付文档.md") for n in names)}  '
          f'含 summary={any(n.endswith("跑分产物与轨迹/summary.json") for n in names)}')

    dd, idx, row = read_row()
    print('\n=== 上传前 ===')
    for fname, fid, f, mode in TARGETS:
        a = atts_of(dd, idx, row, fname)
        print(f'  [{fname}] {fid}  附件数={len(a)}  删除策略={mode}')
        for x in a:
            print(f'     - {x.get("name")}  {x.get("size")}B  token={x.get("file_token")}')

    if not APPLY:
        print('\n（DRY-RUN 结束；加 --apply 执行）')
        return 0

    for fname, fid, f, mode in TARGETS:
        dd, idx, row = read_row()
        for x in atts_of(dd, idx, row, fname):
            if mode == 'same-name' and x.get('name') != f.name:
                print(f'  [跳过] {fname} 保留非同名的 {x.get("name")}')
                continue
            rc, out, err = lark('base', '+record-remove-attachment', '--base-token', BT,
                                '--table-id', TB, '--record-id', REC, '--field-id', fid,
                                '--file-token', x['file_token'], '--as', 'user',
                                '--format', 'json', yes=True)
            print(f'  [删除] {fname} {x.get("name")}({x.get("size")}B) rc={rc}')
        rc, out, err = lark('base', '+record-upload-attachment', '--base-token', BT,
                            '--table-id', TB, '--record-id', REC, '--field-id', fid,
                            '--file', str(f), '--as', 'user', '--format', 'json')
        print(f'  [上传] {fname} {f.name} rc={rc}  {(out or err)[:120]}')

    dd, idx, row = read_row()
    print('\n=== 上传后 ===')
    ok = True
    for fname, fid, f, mode in TARGETS:
        a = atts_of(dd, idx, row, fname)
        print(f'  [{fname}] 附件数={len(a)}')
        hit = False
        for x in a:
            flag = '✅ 本次新包' if x.get('size') == f.stat().st_size else '⚠ 其他'
            hit |= x.get('size') == f.stat().st_size
            print(f'     - {x.get("name")}  {x.get("size")}B  {flag}')
        if not hit:
            ok = False
            print(f'     [ERR] 未找到 size={f.stat().st_size} 新包')
    print('\n结论:', '全部字段终态正确 ✅' if ok else '存在字段未达预期 ⚠')
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
