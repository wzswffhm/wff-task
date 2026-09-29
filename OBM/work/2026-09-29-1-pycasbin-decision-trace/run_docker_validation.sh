#!/usr/bin/env bash
# Local deepSWE validation matrix: NOP (unpatched) -> reward 0, ORACLE (reference
# patch applied) -> reward 1. Mirrors the official verify_agent_patch.py flow,
# which builds the app image offline, derives the verifier image from it, and
# reads the reward the verifier emits.
set -uo pipefail

export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"
export MSYS_NO_PATHCONV=1

PKG="C:/Users/Administrator/Desktop/OBM/output/deepSWE_2026-09-29-1-pycasbin-decision-trace"
WORK="C:/Users/Administrator/Desktop/OBM/work/2026-09-29-1-pycasbin-decision-trace"
OUTROOT="/c/Users/Administrator/Desktop/OBM/work/2026-09-29-1-pycasbin-decision-trace/verify"

run_case() {
  local case="$1" appdir="$2" outdir="$3"
  echo "=================== CASE: ${case} ==================="
  rm -rf "$outdir"; mkdir -p "$outdir"
  echo "--- app build ---"
  if ! docker build --network=none -t "obm-${case}-app:latest" "$appdir" > "$outdir/APP_BUILD.log" 2>&1; then
    echo "APP BUILD FAILED"; tail -25 "$outdir/APP_BUILD.log"; return 1
  fi
  echo "--- verifier build ---"
  if ! docker build --network=none --build-arg APP_IMAGE="obm-${case}-app:latest" \
        -t "obm-${case}-verifier:latest" "$PKG/sources/verifier" > "$outdir/VERIFIER_BUILD.log" 2>&1; then
    echo "VERIFIER BUILD FAILED"; tail -25 "$outdir/VERIFIER_BUILD.log"; return 1
  fi
  echo "--- verifier run ---"
  docker run --rm --network=none "obm-${case}-verifier:latest" > "$outdir/VERIFIER_RUN.log" 2>&1
  echo "container exit=$?"
  grep -E '^REWARD=' "$outdir/VERIFIER_RUN.log" || echo "NO REWARD LINE"
  echo "--- summary (reward json) ---"
  sed -n '/^{/,/^}/p' "$outdir/VERIFIER_RUN.log" | head -30
}

mkdir -p "$OUTROOT"

# ---------- NOP: pristine base commit, feature absent ----------
run_case nop "$PKG/sources/app" "$OUTROOT/nop"

# ---------- ORACLE: reference patch applied ----------
# Use a Windows-style staging path: with MSYS_NO_PATHCONV=1, Docker Desktop
# cannot resolve POSIX build-context paths such as /tmp/...
ORACLE_APP="$WORK/oracle-app-$(date +%H%M%S)"
cp -r "$PKG/sources/app" "$ORACLE_APP"
(
  cd "$ORACLE_APP" || exit 1
  git apply --whitespace=nowarn "$WORK/solution.patch" || exit 1
  echo "oracle patch applied"
) || { echo "ORACLE PATCH APPLY FAILED"; exit 1; }
run_case oracle "$ORACLE_APP" "$OUTROOT/oracle"

echo "=================== DONE ==================="
