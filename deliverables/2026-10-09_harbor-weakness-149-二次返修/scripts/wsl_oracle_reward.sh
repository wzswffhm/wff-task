#!/usr/bin/env bash
T=/home/wff/harbor-runs/FIN3-WKN-149-fix9/trials-oracle/FIN3-WKN-149__DRcKq7u
echo "时间: $(date '+%F %T')"
echo "=== reward.json ==="
cat "$T/verifier/reward.json" 2>/dev/null
echo ""
echo "=== graded 目录 ==="
ls -la "$T/verifier/graded/" 2>/dev/null
echo "=== reward-details 存在? ==="
if [ -f "$T/verifier/graded/reward-details.json" ]; then
  echo "存在，大小 $(stat -c%s "$T/verifier/graded/reward-details.json") B"
  # 提取 score 与零分判据
  python3 -c "
import json
d=json.load(open('$T/verifier/graded/reward-details.json'))
r=d.get('reward', d)
print('score:', r.get('score') or r.get('graded_score'))
cs=r.get('criteria', [])
zeros=[c['id'] for c in cs if float(c.get('value',1))<0.5]
print('零分(<0.5):', zeros)
"
fi
echo "=== rewardkit 进程数(149) ==="
ps aux | grep rewardkit | grep -v grep | grep -v FIN3-WKN-150 | wc -l
echo "=== oracle.out 尾 ==="
tail -8 /home/wff/harbor-runs/FIN3-WKN-149-fix9/oracle_fix9.out
