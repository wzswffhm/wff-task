#!/bin/bash
# 平台固定模板，请勿改动，直接使用本模板。
# 来源：《外发版-评测题包交付规范 v4》附录 A.1。以官方最新版本为准。
set -uo pipefail

mkdir -p /logs/verifier/graded /logs/verifier/gating

rewardkit /tests/graded --workspace /app --output /logs/verifier/graded/reward.json
graded_rc=$?

rewardkit /tests/gating --workspace /app --output /logs/verifier/gating/reward.json
gating_rc=$?

python3 /tests/finalize.py \
  --graded /logs/verifier/graded/reward.json --graded-rc "$graded_rc" \
  --gating /logs/verifier/gating/reward.json --gating-rc "$gating_rc" \
  --out /logs/verifier/reward.json
