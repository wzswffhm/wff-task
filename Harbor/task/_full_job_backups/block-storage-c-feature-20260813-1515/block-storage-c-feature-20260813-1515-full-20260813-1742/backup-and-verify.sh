#!/usr/bin/env bash
# Full backup + verify deliverable jobs/ layout (P0 gate).
set -u
TASK=/home/wff/harbor/block-storage-c-feature-20260813-1515
TS=$(date +%Y%m%d-%H%M)
BACKUP=/home/wff/harbor/task/_full_job_backups/block-storage-c-feature-20260813-1515
mkdir -p "$BACKUP"
cp -r "$TASK" "$BACKUP/block-storage-c-feature-20260813-1515-full-$TS"
echo "=== 全量备份完成: $BACKUP/block-storage-c-feature-20260813-1515-full-$TS ==="

echo "=== 交付 jobs/ 结构 ==="
ls "$TASK/jobs/"
echo "--- baseline ---"
cat "$TASK/jobs/baseline"/*/verifier/reward.txt 2>/dev/null | head -2
echo "--- oracle ---"
cat "$TASK/jobs/oracle"/*/verifier/reward.txt 2>/dev/null | head -2
grep -o '"programmatic_score": [0-9.]*' "$TASK/jobs/oracle"/*/verifier/details.json 2>/dev/null | head -1
echo "--- selected-trials 数量 ---"
ls -d "$TASK/jobs/selected-trials"/trial-* 2>/dev/null | wc -l
echo "--- quality.toml 非空壳检查 ---"
grep -c "\[judge\]\|\[\[criterion\]\]" "$TASK/tests/quality.toml"
echo "--- test.sh 含 rewardkit ---"
grep -c "rewardkit" "$TASK/tests/test.sh"
echo "--- manifest selected ---"
python3 -c "import json; d=json.load(open('$TASK/jobs/difficulty-manifest.json')); print('selected:', len(d['selected_trials']), 'r1:', sum(1 for s in d['selected_trials'] if s['reward']==1.0), 'r0:', sum(1 for s in d['selected_trials'] if s['reward']==0.0))"
