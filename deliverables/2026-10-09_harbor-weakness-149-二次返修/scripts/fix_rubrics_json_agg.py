# -*- coding: utf-8 -*-
"""给 rubrics.json 的 metadata.scoring 补 aggregation 字段（与 rubrics.toml [scoring] 对齐）。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149\rubrics.json')

data = json.loads(P.read_text(encoding='utf-8'))
sc = data.setdefault('metadata', {}).setdefault('scoring', {})
had = 'aggregation' in sc
sc.setdefault('aggregation', 'weighted_mean')

# 保持原文件缩进风格（indent=1）
P.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
print(f'  aggregation 原已存在={had}  当前={sc["aggregation"]}')
print(f'  scoring 键: {list(sc.keys())}')
print(f'  判据数={data.get("metadata",{}).get("criteria_count")}  '
      f'items={len(data.get("items", []))}')
