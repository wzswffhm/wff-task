#!/usr/bin/env bash
echo "时间: $(date '+%F %T')"
echo "=== 149 容器内当前判据（claude -p 的 - 'Rxx'）==="
docker exec fin3-wkn-149__drckq7u__env-main-1 ps aux 2>/dev/null | grep -o "\- '[RN][0-9]*'" | head -3
echo "=== 149 容器内 rewardkit 日志尾（判到哪）==="
docker exec fin3-wkn-149__drckq7u__env-main-1 sh -c 'tail -20 /logs/verifier/graded/stderr.txt 2>/dev/null || tail -20 /logs/verifier/test-stdout.txt 2>/dev/null' 2>/dev/null
echo "=== 150 rejudge 状态（是否已完成，减轻并发）==="
docker ps --format '{{.Names}} {{.Status}}' | grep -i rejudge || echo "(150 rejudge 已全部完成)"
