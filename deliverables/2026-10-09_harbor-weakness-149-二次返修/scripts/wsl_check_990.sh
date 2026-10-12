#!/usr/bin/env bash
Z=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/work_fin-b01_20261011_fix9-149.zip
python3 - "$Z" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
base = 'work_fin-b01_20261011_fix9-149/FIN3-WKN-149/'
for rel in ['solution/golden_output/FIN3-WKN-149_风险委员会决策备忘录.md',
            'solution/golden_output/FIN3-WKN-149_reproduce.py']:
    t = z.read(base + rel).decode('utf-8')
    print(f'--- {rel}')
    for i, ln in enumerate(t.splitlines(), 1):
        if '9.90' in ln:
            print(f'  L{i}: {ln.strip()[:200]}')
PY
echo ""
echo "=== 清理 oracle 容器 ==="
docker rm -f fin3-wkn-149__drckq7u__env-main-1 2>&1
echo "=== 复核容器 ==="
docker ps --format '{{.Names}}' | grep -i 149 || echo "(无 149 容器)"
