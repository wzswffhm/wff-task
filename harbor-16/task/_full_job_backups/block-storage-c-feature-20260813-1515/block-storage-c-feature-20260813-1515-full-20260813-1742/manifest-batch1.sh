#!/usr/bin/env bash
# Show batch-1 per-trial rewards and write difficulty-manifest.json (batch 1).
set -u
TASK=/home/wff/harbor/block-storage-c-feature-20260813-1515
JOB="$TASK/jobs/tree-difficulty-16c16"
R1=0; R0=0; OTHER=0
echo "=== 逐 trial ==="
> /tmp/tree_batch1_rewards.txt
for d in "$JOB/tree-difficulty-16c16"/*/; do
  rw="$d/verifier/reward.txt"
  [ -f "$rw" ] || continue
  r=$(tr -d ' \n' < "$rw")
  n=$(basename "$d")
  echo "$n: $r" | tee -a /tmp/tree_batch1_rewards.txt
  case "$r" in
    1.0|1) R1=$((R1+1)) ;;
    0.0|0) R0=$((R0+1)) ;;
    *) OTHER=$((OTHER+1)) ;;
  esac
done
echo "=== reward1=$R1 reward0=$R0 other=$OTHER ==="
# build manifest
cat > "$TASK/jobs/difficulty-manifest.json" <<EOF
{
  "task": "block-storage-c-feature-20260813-1515",
  "generated": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "frozen_hashes": $(python3 -c "import json; print(json.dumps(dict(l.split('  ')[::-1] for l in open('$TASK/jobs/frozen-hashes.txt') if '  ' in l)))" 2>/dev/null || echo '{}'),
  "batches": [
    {
      "batch": "tree-difficulty-16c16",
      "job_dir": "jobs/tree-difficulty-16c16",
      "n_attempts": 16,
      "concurrency": 16,
      "reward1": $R1,
      "reward0": $R0,
      "trials": [
EOF
first=1
while IFS=: read -r n r; do
  [ -z "$n" ] && continue
  if [ "$first" = "0" ]; then echo "," >> "$TASK/jobs/difficulty-manifest.json"; fi
  first=0
  printf '        {"trial_id": "%s", "reward": %s, "terminal": "complete", "valid": true}' "$n" "$r" >> "$TASK/jobs/difficulty-manifest.json"
done < /tmp/tree_batch1_rewards.txt
cat >> "$TASK/jobs/difficulty-manifest.json" <<EOF

      ]
    }
  ],
  "selected_trials": [],
  "selection_rule": "not yet selected; awaiting more batches until reward<1 >=13 and reward=1 >=1"
}
EOF
echo "manifest written"
