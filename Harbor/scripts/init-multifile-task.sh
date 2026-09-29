#!/usr/bin/env bash
# Create new multifile task dir with timestamp, copy nbd workspace from reference.
set -u
TS=$(date +%Y%m%d-%H%M)
TASK="block-storage-c-feature-$TS"
mkdir -p "/home/wff/harbor/$TASK/environment/workspace" \
         "/home/wff/harbor/$TASK/solution" \
         "/home/wff/harbor/$TASK/tests" \
         "/home/wff/harbor/$TASK/jobs"
cp -r /home/wff/harbor/zq2026080704322-block-storage-c-feature-20260809-0031/environment/workspace/nbd \
      "/home/wff/harbor/$TASK/environment/workspace/"
echo "$TASK" > /tmp/cow_task_name.txt
echo "=== task dir: $TASK ==="
ls "/home/wff/harbor/$TASK/environment/workspace/nbd" | head -6
echo "F_MULTIFILE refs: $(grep -c F_MULTIFILE /home/wff/harbor/$TASK/environment/workspace/nbd/nbd-server.c)"
