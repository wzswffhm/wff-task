#!/bin/bash
# gpt5 当前阶段
C=gpt56sol5-152v2__env-main-1
echo "=== service ==="
systemctl is-active g5-gpt5-152v2.service
echo "=== /app/output ==="
docker exec "$C" sh -c 'ls /app/output 2>/dev/null | wc -l' 2>&1
echo "=== 轨迹大小 ==="
docker exec "$C" sh -c 'wc -c < /logs/agent/claude-code.txt' 2>&1
echo "=== 当前进程 ==="
docker exec "$C" sh -c "ps -eo etimes,args --no-headers | grep -E 'claude -p|claude --verbose' | grep -v grep | head -3 | cut -c1-140" 2>&1
echo "=== 判据进程（带 - 'Rxx'） ==="
docker exec "$C" sh -c "ps -eo etimes,args --no-headers | grep 'claude -p' | grep -v grep | head -1 | grep -oE \"- '[A-Z][0-9][0-9]'\" | head -1" 2>&1
echo "=== graded ==="
docker exec "$C" sh -c 'ls -la /logs/verifier/graded/ 2>/dev/null' 2>&1 | head -8
