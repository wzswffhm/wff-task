# -*- coding: utf-8 -*-
"""端到端验证：从飞书下载刚上传的三个包，检查 create_system 与解压权限。"""
import json
import os
import pathlib
import subprocess
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8')
LARK = r"C:\nvm4w\nodejs\lark-cli.cmd"
BT, TB, REC = "QpzNb4fXSamfX6sLloBcPfHNnug", "tblPNrBtjFfwOowN", "rec28himvkSA77"
OUT = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\deliverables'
                   r'\2026-10-09_harbor-weakness-149-二次返修\_feishu_verify_fix11')
OUT.mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
env["LARK_CLI_NO_PROXY"] = "1"


def lark(*args):
    p = subprocess.run([LARK] + list(args), capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=env)
    return p.returncode, (p.stdout or ''), (p.stderr or '')


rc, out, err = lark('base', '+record-list', '--base-token', BT, '--table-id', TB,
                    '--page-size', '100', '--as', 'user', '--format', 'json')
dd = json.loads(out)['data']
idx = {n: i for i, n in enumerate(dd['fields'])}
row = dd['data'][dd['record_id_list'].index(REC)]

print('=== 从飞书下载三个附件 ===')
files = {}
for field in ['题目附件信息', '标准答案附件信息', '交付物']:
    for a in (row[idx[field]] or []):
        name, tok = a.get('name'), a.get('file_token')
        dst = OUT / name
        rc, out, err = lark('base', '+record-download-attachment', '--base-token', BT,
                            '--table-id', TB, '--record-id', REC, '--file-token', tok,
                            '--output', str(dst), '--as', 'user', '--format', 'json')
        print(f'  [{field}] {name} {a.get("size")}B -> rc={rc} 下载={dst.stat().st_size if dst.exists() else 0}B')
        files[field] = dst

print('\n=== create_system / 高位 mode 检查（飞书下载件）===')
for field, f in files.items():
    if not f.exists():
        continue
    z = zipfile.ZipFile(f)
    cs = {}
    for i in z.infolist():
        cs.setdefault(i.create_system, 0)
        cs[i.create_system] += 1
    shs = [(i.filename, i.create_system, oct(i.external_attr >> 16))
           for i in z.infolist() if i.filename.endswith('.sh')]
    print(f'  {f.name}: create_system分布={cs}')
    for n, c, m in shs:
        print(f'     .sh create_system={c} mode={m}  {n.split("/")[-1]}')

print('\n=== 真实解压器复验（busybox unzip，alpine）===')
names = [f.name for f in files.values() if f.exists()]
script = ';'.join(
    f'rm -rf /t; mkdir -p /t; cd /t; busybox unzip -q "/z/{n}"; '
    f'echo "--- {n}"; for f in $(busybox find /t -name "*.sh"|sort); do '
    f'echo "    $(busybox stat -c %a $f)  $(basename $f)"; done'
    for n in names)
p = subprocess.run(['wsl', '-d', 'Ubuntu', '--', 'docker', 'run', '--rm',
                    '-v', f'/mnt/c/Users/Administrator/Desktop/wff-task/deliverables/'
                          f'2026-10-09_harbor-weakness-149-二次返修/_feishu_verify_fix11:/z:ro',
                    'alpine:3.20', 'sh', '-c', script],
                   capture_output=True, text=True, encoding='utf-8', errors='replace')
print(p.stdout or p.stderr)
