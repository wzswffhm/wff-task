#!/usr/bin/env bash
# End-to-end validation of the Seed verification path:
#   pristine sources/app image + verifier that applies /logs/artifacts/model.patch
#   NOP-E2E:   empty model.patch  -> reward 0
#   ORACLE-E2E: model.patch = solution.patch -> grader applies it -> reward 1
set -uo pipefail

export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"
export MSYS_NO_PATHCONV=1

PKG="C:/Users/Administrator/Desktop/OBM/output/deepSWE_2026-09-29-1-pycasbin-decision-trace"
WORK="C:/Users/Administrator/Desktop/OBM/work/2026-09-29-1-pycasbin-decision-trace"
OUTROOT="$WORK/verify"

APP_IMAGE="obm-nop-app:latest"   # pristine baseline app (built by the NOP case)

echo "=== rebuilding verifier image with updated grader ==="
docker build --network=none --build-arg APP_IMAGE="$APP_IMAGE" -t obm-e2e-verifier:latest "$PKG/sources/verifier" > "$OUTROOT/VERIFIER_BUILD_E2E.log" 2>&1 \
  || { echo "VERIFIER BUILD FAILED"; tail -25 "$OUTROOT/VERIFIER_BUILD_E2E.log"; exit 1; }
echo "verifier image rebuilt"

e2e_case() {
  local case="$1" patch_src="$2"
  local stage="$WORK/e2e-$case"
  rm -rf "$stage"; mkdir -p "$stage/artifacts" "$stage/logs"
  if [ -n "$patch_src" ]; then
    cp "$patch_src" "$stage/artifacts/model.patch"
  else
    : > "$stage/artifacts/model.patch"
  fi
  echo "=================== E2E CASE: ${case} ==================="
  docker run --rm --network=none \
    -v "$stage/artifacts:/logs/artifacts" \
    -v "$stage/logs:/logs/verifier" \
    obm-e2e-verifier:latest > "$OUTROOT/VERIFIER_RUN_E2E_${case}.log" 2>&1
  echo "container exit=$?"
  grep -E '^(REWARD=|PATCH_PREPARE=)' "$OUTROOT/VERIFIER_RUN_E2E_${case}.log"
  grep -m1 '"reward"' "$stage/logs/reward.json" 2>/dev/null || echo "(no reward.json)"
}

e2e_case nop ""
e2e_case oracle "$WORK/solution.patch"

echo "=================== E2E DONE ==================="
