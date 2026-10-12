# -*- coding: utf-8 -*-
"""把 fix9 修复后的题包文件同步到批次目录（覆盖 fix8 版）。"""
import hashlib
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')
SRC = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149')
BATCH = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                     r'\work_fin-b01_20261009_fix8-149\FIN3-WKN-149')

# 批次题包内需同步的文件（相对 src/batch）
FILES = [
    'rubrics.json',
    'task.toml',
    'solution/golden_output/FIN3-WKN-149_reproduce.py',
    'solution/golden_output/FIN3-WKN-149_风险委员会决策备忘录.md',
    'solution/golden_output/FIN3-WKN-149_charts/FIN3-WKN-149_chart01_数据覆盖与缺口.png',
    'solution/golden_output/FIN3-WKN-149_charts/FIN3-WKN-149_chart02_历史风险总览.png',
    'solution/golden_output/FIN3-WKN-149_charts/FIN3-WKN-149_chart03_情景识别与校准.png',
    'solution/golden_output/FIN3-WKN-149_charts/FIN3-WKN-149_chart04_方案决策与执行.png',
    'solution/golden_output/FIN3-WKN-149_charts/FIN3-WKN-149_chart05_监测指标触发状态.png',
    'tests/rubrics.toml',
    'tests/__golden_output/FIN3-WKN-149_reproduce.py',
    'tests/__golden_output/FIN3-WKN-149_风险委员会决策备忘录.md',
    'tests/__golden_output/FIN3-WKN-149_charts/FIN3-WKN-149_chart01_数据覆盖与缺口.png',
    'tests/__golden_output/FIN3-WKN-149_charts/FIN3-WKN-149_chart02_历史风险总览.png',
    'tests/__golden_output/FIN3-WKN-149_charts/FIN3-WKN-149_chart03_情景识别与校准.png',
    'tests/__golden_output/FIN3-WKN-149_charts/FIN3-WKN-149_chart04_方案决策与执行.png',
    'tests/__golden_output/FIN3-WKN-149_charts/FIN3-WKN-149_chart05_监测指标触发状态.png',
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


ok = True
for rel in FILES:
    src, dst = SRC / rel, BATCH / rel
    if not src.is_file():
        print(f'  [MISS src] {rel}')
        ok = False
        continue
    before = sha(dst) if dst.exists() else 'NEW'
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    after = sha(dst)
    match = after == sha(src)
    ok &= match
    print(f'  {"OK" if match else "FAIL"} {rel}  {before} -> {after}')

# 校验批次 rubrics 含 aggregation
toml = (BATCH / 'tests' / 'rubrics.toml').read_text(encoding='utf-8')
print(f'\n[校验] 批次 rubrics.toml 含 aggregation={"aggregation" in toml}  '
      f'[scoring]={"[scoring]" in toml}')
import json
j = json.loads((BATCH / 'rubrics.json').read_text(encoding='utf-8'))
print(f'[校验] 批次 rubrics.json aggregation={j["metadata"]["scoring"].get("aggregation")}')
sys.exit(0 if ok else 1)
