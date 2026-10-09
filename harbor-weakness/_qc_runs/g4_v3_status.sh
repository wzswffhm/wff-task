#!/bin/bash
# G4 v3 进度
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g4-152v3
echo "=== service ==="
systemctl is-active g4-152v3.service
echo "=== oracle.log 尾部 ==="
tail -8 "$R/oracle.log" 2>/dev/null
echo "=== reward ==="
find "$R/trials" -maxdepth 3 -name reward.json 2>/dev/null | while read -r f; do tr -d '\n' < "$f"; echo; done
echo "=== trial 目录 ==="
ls "$R/trials" 2>/dev/null
