#!/bin/bash
# Harbor verifier for block-storage-c-feature-20260812-1459 (nbd-server COW export).
# final reward = programmatic score (snapshotted right after pytest, so a later
# rewardkit invocation can never overwrite the deterministic result).
set -euo pipefail

TESTS_DIR="/tests"
WORKSPACE="${WORKSPACE:-/workspace/nbd}"
REWARD_DIR="/logs/verifier"
SCRATCH="/var/tmp"
REWARDKIT_VERSION="0.1.4"
PROG_GATE="1.0"

mkdir -p "$REWARD_DIR" "$SCRATCH"
export TESTS_DIR WORKSPACE PYTHONPATH="$TESTS_DIR${PYTHONPATH:+:$PYTHONPATH}"

PY=python3
if [[ -x /opt/harbor-venv/bin/python ]]; then
  PY=/opt/harbor-venv/bin/python
fi

echo "=== [0/3] Rebuilding nbd-server from agent workspace ==="
cd "$WORKSPACE"
make -j"$(nproc)" nbd-server > "$SCRATCH/make_out.txt" 2>&1 || true
if [ ! -x ./nbd-server ]; then
  echo "0.0" > "$REWARD_DIR/reward.txt"
  echo '{"reward": 0.0, "crash": "nbd-server rebuild failed"}' > "$REWARD_DIR/details.json"
  exit 1
fi
echo "nbd-server rebuilt OK"

echo "=== [1/3] Running programmatic verifier (pytest --ctrf) ==="
cd "$WORKSPACE"
"$PY" -m pytest -q "$TESTS_DIR/test_outputs.py" --ctrf "$REWARD_DIR/ctrf.json" > "$SCRATCH/pytest_out.txt" 2>&1 || true
echo "pytest finished (details kept in scratch)"

PROG_JSON="$SCRATCH/programmatic_score.json"
if [ ! -f "$PROG_JSON" ]; then
  echo "0.0" > "$REWARD_DIR/reward.txt"
  echo '{"reward": 0.0, "crash": "no programmatic output"}' > "$REWARD_DIR/details.json"
  exit 1
fi

SNAP_JSON="$SCRATCH/programmatic_score.snapshot.json"
cp -f "$PROG_JSON" "$SNAP_JSON"

PROG_SCORE="$("$PY" -c "import json; d=json.load(open('$SNAP_JSON')); print(d.get('programmatic_score', 0.0))")"
PASSED="$("$PY" -c "import json; d=json.load(open('$SNAP_JSON')); print(d.get('tests_passed', 0))")"
TOTAL="$("$PY" -c "import json; d=json.load(open('$SNAP_JSON')); print(d.get('tests_total', 0))")"
echo "programmatic_score = $PROG_SCORE ($PASSED/$TOTAL)"

echo "=== [2/3] Short-circuit check (prog < $PROG_GATE -> skip judge) ==="
IS_SHORT="$("$PY" -c "print(1 if float('$PROG_SCORE') < $PROG_GATE else 0)")"
if [ "$IS_SHORT" = "1" ]; then
  echo "0.0" > "$REWARD_DIR/reward.txt"
  python3 - "$SNAP_JSON" "$REWARD_DIR/details.json" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
with open(src) as f:
    prog = json.load(f)
json.dump({
    "reward": 0.0, "final_score": 0.0,
    "programmatic_score": 0.0, "test_pass_rate": 0.0,
    "judge_skipped_reason": "programmatic_score below gate (deterministic failure)",
    "tests_passed": prog.get("tests_passed", 0),
    "tests_total": prog.get("tests_total", 0),
}, open(dst, "w"), indent=2)
PY
  exit 1
fi

echo "=== [3/3] Invoking rewardkit judge ==="
export LITELLM_DROP_PARAMS=True
export LITELLM_MODIFY_PARAMS=True
: "${ANTHROPIC_API_KEY:=${DASHSCOPE_API_KEY:-${OPENAI_API_KEY:-}}}"
: "${ANTHROPIC_API_BASE:=https://dashscope.aliyuncs.com/apps/anthropic}"
export ANTHROPIC_API_KEY ANTHROPIC_API_BASE

set +e
UVX_CMD=(uvx --from "harbor-rewardkit==$REWARDKIT_VERSION" rewardkit
  --workspace "$WORKSPACE"
  --output "$SCRATCH/quality_score.json"
  "$TESTS_DIR")
echo "Running: ${UVX_CMD[*]}"
"${UVX_CMD[@]}"
UVX_RC=$?
set -e

QUALITY_SCORE="0.0"
if [ -f "$SCRATCH/quality_score.json" ]; then
  QUALITY_SCORE="$("$PY" -c "
import json
d = json.load(open('$SCRATCH/quality_score.json'))
v = d.get('score', d.get('weighted_mean'))
if v is None:
    nums = [x for x in d.values() if isinstance(x, (int, float))]
    v = nums[0] if nums else 0.0
print(v)
")"
fi
echo "judge/quality score = $QUALITY_SCORE"

FINAL_REWARD="$PROG_SCORE"
echo "$FINAL_REWARD" > "$REWARD_DIR/reward.txt"

python3 - "$SNAP_JSON" "$SCRATCH/quality_score.json" "$REWARD_DIR/details.json" "$FINAL_REWARD" "$PROG_SCORE" "$QUALITY_SCORE" "$UVX_RC" <<'PY'
import json, sys
prog_path, qual_path, dst_path, final, prog, qual, uvx_rc = sys.argv[1:]
with open(prog_path) as f:
    prog_obj = json.load(f)
qual_obj = {}
try:
    with open(qual_path) as f:
        qual_obj = json.load(f)
except FileNotFoundError:
    qual_obj = {"error": "quality output file missing"}
json.dump({
    "reward": float(final), "final_score": float(final),
    "programmatic_score": float(sys.argv[5]),
    "quality_score": float(sys.argv[6]),
    "reward_formula": "reward = programmatic_score (snapshot; quality recorded as evidence)",
    "rewardkit_exit_code": int(sys.argv[7]),
    "rewardkit_details": qual_obj,
    "tests_passed": prog_obj.get("tests_passed", 0),
    "tests_total": prog_obj.get("tests_total", 0),
}, open(dst_path, "w"), indent=2, ensure_ascii=False)
PY

echo "Wrote final reward = $FINAL_REWARD"
RC="$("$PY" -c "print(0 if $FINAL_REWARD >= 0.8 else 1)")"
exit "$RC"
