#!/usr/bin/env bash
# Init treefiles task dir (clean full source from reference), archive multifile attempt.
set -u
TS=$(date +%Y%m%d-%H%M)
TASK="block-storage-c-feature-$TS"
# archive the multifile attempt dir
mv /home/wff/harbor/block-storage-c-feature-20260813-1513 /home/wff/harbor/_failed_project_backups/ 2>/dev/null || true
mkdir -p "/home/wff/harbor/_failed_project_backups"
mv /home/wff/harbor/block-storage-c-feature-20260813-1513 "/home/wff/harbor/_failed_project_backups/" 2>/dev/null || true
mkdir -p "/home/wff/harbor/$TASK/environment/workspace" "/home/wff/harbor/$TASK/solution" "/home/wff/harbor/$TASK/tests" "/home/wff/harbor/$TASK/jobs"
cp -r /home/wff/harbor/zq2026080704322-block-storage-c-feature-20260809-0031/environment/workspace/nbd "/home/wff/harbor/$TASK/environment/workspace/"
echo "$TASK" > /tmp/mf_task_name.txt
echo "=== task dir: $TASK ==="
cd "/home/wff/harbor/$TASK/environment/workspace/nbd"
sed -i 's/\r$//' nbd-server.c treefiles.c 2>/dev/null
cp nbd-server.c /tmp/tf-nbd-server.c.full
cp treefiles.c /tmp/tf-treefiles.c.full
echo "treefiles.c lines: $(wc -l < treefiles.c); F_TREEFILES refs: $(grep -c F_TREEFILES nbd-server.c)"
