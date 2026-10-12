# -*- coding: utf-8 -*-
"""把 rubrics.json 也同步到 WSL 任务目录。"""
import hashlib
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')
WIN = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149\rubrics.json')
WSL = pathlib.Path(r'\\wsl.localhost\Ubuntu\home\wff\harbor-tasks-fix8\FIN3-WKN-149\rubrics.json')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]

b = sha(WSL) if WSL.exists() else 'MISS'
shutil.copy2(WIN, WSL)
a = sha(WSL)
print(f'rubrics.json: win={sha(WIN)}  wsl_before={b}  wsl_after={a}  match={sha(WIN)==a}')
import json
d = json.loads(WSL.read_text(encoding='utf-8'))
print(f'  WSL侧 aggregation={d["metadata"]["scoring"].get("aggregation")}  items={len(d["items"])}')
