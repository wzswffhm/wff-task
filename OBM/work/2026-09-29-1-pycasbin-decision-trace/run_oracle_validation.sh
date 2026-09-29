#!/usr/bin/env bash
# ORACLE case only: build app with reference patch applied, derive verifier, expect reward=1.
# Uses Windows-style build-context paths because Docker Desktop cannot resolve Git Bash
# POSIX paths such as /tmp/... when MSYS_NO_PATHCONV=1 is set.
set -uo pipefail

export PATH="/c/Program Files/Docker/Docker/resources/bin:$PATH"
export MSYS_NO_PATHCONV=1

PKG="C:/Users/Administrator/Desktop/OBM/output/deepSWE_2026-09-29-1-pycasbin-decision-trace"
WORK="C:/Users/Administrator/Desktop/OBM/work/2026-09-29-1-pycasbin-decision-trace"
ORACLE_APP="$WORK/oracle-app-$(date +%H%M%S)"
OUTDIR="$WORK/verify/oracle"

mkdir -p "$OUTDIR"
echo "=================== CASE: oracle ==================="
echo "--- staging oracle app at $ORACLE_APP ---"
cp -r "$PKG/sources/app" "$ORACLE_APP" || { echo "COPY FAILED"; exit 1; }

(
  cd "$ORACLE_APP" || exit 1
  git apply --whitespace=nowarn "$WORK/solution.patch" || exit 1
  echo "oracle patch applied"
) || { echo "PATCH APPLY FAILED"; exit 1; }

echo "--- app build ---"
if ! docker build --network=none -t "obm-oracle-app:latest" "$ORACLE_APP" > "$OUTDIR/APP_BUILD.log" 2>&1; then
  echo "APP BUILD FAILED"; tail -25 "$OUTDIR/APP_BUILD.log"; exit 1
fi

echo "--- verifier build ---"
if ! docker build --network=none --build-arg APP_IMAGE="obm-oracle-app:latest" \
      -t "obm-oracle-verifier:latest" "$PKG/sources/verifier" > "$OUTDIR/VERIFIER_BUILD.log" 2>&1; then
  echo "VERIFIER BUILD FAILED"; tail -25 "$OUTDIR/VERIFIER_BUILD.log"; exit 1
fi

echo "--- verifier run ---"
docker run --rm --network=none "obm-oracle-verifier:latest" > "$OUTDIR/VERIFIER_RUN.log" 2>&1
echo "container exit=$?"
grep -E '^REWARD=' "$OUTDIR/VERIFIER_RUN.log" || echo "NO REWARD LINE"
echo "--- summary (reward json) ---"
sed -n '/^{/,/^}/p' "$OUTDIR/VERIFIER_RUN.log" | head -20

echo "=================== DONE ==================="
