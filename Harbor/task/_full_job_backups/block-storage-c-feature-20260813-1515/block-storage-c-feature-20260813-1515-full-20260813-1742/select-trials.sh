#!/usr/bin/env bash
# Select 16 trials deterministically (all 13 reward=0 + first 3 reward=1 by
# trial name) and assemble deliverable jobs/ layout:
#   jobs/baseline + jobs/oracle + jobs/selected-trials/ + manifest
set -u
TASK=/home/wff/harbor/block-storage-c-feature-20260813-1515
B1="$TASK/jobs/tree-difficulty-16c16/tree-difficulty-16c16"
B2="$TASK/jobs/tree-difficulty-16c16-b2/tree-difficulty-16c16-b2"
SEL="$TASK/jobs/selected-trials"
rm -rf "$SEL"
mkdir -p "$SEL"

# collect candidates: reward|source|trialdir
> /tmp/tree_cand.txt
for JOB in "$B1" "$B2"; do
  SRC=$(basename "$(dirname "$JOB")")
  for d in "$JOB"/*/; do
    rw="$d/verifier/reward.txt"
    [ -f "$rw" ] || continue
    r=$(tr -d ' \n' < "$rw")
    echo "$r|$SRC|$d" >> /tmp/tree_cand.txt
  done
done

# selection: 15 x reward=0 + 1 x reward=1 (skill: reward<1 >=13 AND reward=1 >=1)
R0=$(grep -c "^0.0|" /tmp/tree_cand.txt)
echo "candidates: reward0=$R0 reward1=$(grep -c '^1.0|' /tmp/tree_cand.txt)"
# deterministic: 15 reward=0 (by trial name), 1 reward=1 (by trial name)
grep "^0.0|" /tmp/tree_cand.txt | sort -t'|' -k3 | head -n 15 > /tmp/tree_sel0.txt
grep "^1.0|" /tmp/tree_cand.txt | sort -t'|' -k3 | head -n 1 > /tmp/tree_sel1.txt
cat /tmp/tree_sel0.txt /tmp/tree_sel1.txt > /tmp/tree_sel.txt

echo "=== 选中的 16 条 ==="
N=0
while IFS='|' read -r r src d; do
  N=$((N+1))
  t=$(basename "$d")
  mkdir -p "$SEL/$(printf 'trial-%02d__%s' "$N" "${t##*__}")"
  cp -r "$d/." "$SEL/$(printf 'trial-%02d__%s' "$N" "${t##*__}")/"
  echo "  $N. $src / ${t##*__} reward=$r"
done < /tmp/tree_sel.txt
echo "=== selected-trials 目录数: $(ls -d "$SEL"/trial-* | wc -l) ==="
