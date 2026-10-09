#!/bin/bash
# opus v3 阶段
C=opus48-152v3__env-main-1
echo -n "  output: "; docker exec "$C" sh -c 'ls /app/output 2>/dev/null | wc -l' 2>/dev/null
echo -n "  agent进程: "; docker exec "$C" sh -c "ps -eo args --no-headers | grep -c 'claude --verbose'" 2>/dev/null
echo -n "  判官进程: "; docker exec "$C" sh -c "ps -eo args --no-headers | grep -c 'claude -p'" 2>/dev/null
echo -n "  当前判据: "; docker exec "$C" sh -c "ps -eo etimes,args --no-headers | grep 'claude -p' | grep -v grep | head -1" 2>/dev/null | grep -oE "[RN][0-9]{2}" | head -1
echo -n "  service: "; systemctl is-active g5-v3-opus.service
date '+%F %T'
