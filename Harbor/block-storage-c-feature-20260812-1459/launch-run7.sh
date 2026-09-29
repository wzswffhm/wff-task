#!/usr/bin/env bash
# Archive run-6 results, verify workspace is cow-removed, launch run 7.
set -u
TASK=/home/wff/harbor/block-storage-c-feature-20260812-1459
# 1) archive previous results (16x 0.0)
if [ -d "$TASK/results" ]; then
  mv "$TASK/results" "$TASK/results-run6-16x0.0"
  echo "archived run6 results -> results-run6-16x0.0"
fi
# 2) verify workspace is cow-removed
n=$(grep -c "copyonwrite_prepare" "$TASK/environment/workspace/nbd/nbd-server.c" || true)
echo "copyonwrite_prepare refs: $n (must be 0)"
if [ "$n" != "0" ]; then
  echo "FIXING workspace: reverse oracle.patch from reference full source"
  cd "$TASK/environment/workspace/nbd" || exit 1
  cp /home/wff/harbor/zq2026080704322-block-storage-c-feature-20260809-0031/environment/workspace/nbd/nbd-server.c nbd-server.c
  cp /home/wff/harbor/zq2026080704322-block-storage-c-feature-20260809-0031/environment/workspace/nbd/nbdsrv.h nbdsrv.h
  sed -i 's/\r$//' nbd-server.c nbdsrv.h
  patch -p1 -R < "$TASK/solution/oracle.patch"
  echo "fixed, refs now: $(grep -c copyonwrite_prepare nbd-server.c)"
fi
# 3) launch run 7
bash /tmp/launch-cow.sh
echo "launched run 7"
