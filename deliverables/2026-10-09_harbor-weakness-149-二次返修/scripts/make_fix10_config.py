# -*- coding: utf-8 -*-
"""生成 fix10（本轮：Oracle 同源产物补跑 + 根交付说明移位）的 oracle config。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
SRC = pathlib.Path(r'C:\Users\Administrator\.wff-creds\fin149_fix8_configs\oracle.json')
DST = pathlib.Path(r'C:\Users\Administrator\.wff-creds\fin149_fix10_configs')
DST.mkdir(exist_ok=True)
c = json.loads(SRC.read_text(encoding='utf-8'))
c['task']['path'] = '/home/wff/harbor-tasks-fix8/FIN3-WKN-149'
c['trials_dir'] = '/home/wff/harbor-runs/FIN3-WKN-149-fix10/trials-oracle'
(DST / 'oracle.json').write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'[OK] {DST/"oracle.json"}')
print(json.dumps(c, ensure_ascii=False, indent=2)[:400])
