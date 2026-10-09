#!/bin/bash
# oracle-152v3 当前阶段
C=oracle-152v3__env-main-1
echo "=== /app/output ==="
docker exec "$C" sh -c 'ls /app/output 2>/dev/null | wc -l' 2>&1
echo "=== 阶段 ==="
docker exec "$C" sh -c "ps -eo args --no-headers | grep -c 'claude --verbose'" 2>/dev/null | xargs echo "  agent进程:"
docker exec "$C" sh -c "ps -eo etimes,args --no-headers | grep 'claude -p' | grep -v grep | head -1 | cut -c1-80" 2>/dev/null
echo "=== 轨迹 ==="
docker exec "$C" sh -c 'wc -c < /logs/agent/claude-code.txt 2>/dev/null' 2>&1
echo "=== graded ==="
docker exec "$C" sh -c 'ls /logs/verifier/graded/ 2>/dev/null' 2>&1 | head -6
