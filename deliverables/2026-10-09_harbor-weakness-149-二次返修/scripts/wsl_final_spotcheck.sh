#!/usr/bin/env bash
echo "=== 批次包内金标备忘录关键数值 ==="
Z=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/work_fin-b01_20261011_fix9-149.zip
python3 - "$Z" <<'PY'
import sys, zipfile, re
z = zipfile.ZipFile(sys.argv[1])
memo = z.read('work_fin-b01_20261011_fix9-149/FIN3-WKN-149/solution/golden_output/'
              'FIN3-WKN-149_风险委员会决策备忘录.md').decode('utf-8')
for pat in ['-10.16%', '-7.46%', '-5.56%', '18.38', '52.08', '5.73%']:
    print(f'  含 {pat}: {pat in memo}')
for bad in ['9.90%', '7.03%', '5.05%', '15.19', '50.77']:
    print(f'  旧值 {bad} 残留: {bad in memo}')
print(f'  备忘录行数: {len(memo.splitlines())}')
PY
echo ""
echo "=== 残留容器/进程清理 ==="
docker ps --format '{{.Names}} {{.Status}}' | grep -iE '149|rejudge' || echo "(无 149 相关容器)"
pkill -f 'run_rejudge_149_fix9' 2>/dev/null && echo "已清理 rejudge 主进程" || echo "(rejudge 主进程已退出)"
echo ""
echo "=== 150 并发任务状态（不影响）==="
docker ps --format '{{.Names}}' | grep -c rejudge-FIN3-WKN-150 || true
