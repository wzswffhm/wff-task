#!/bin/bash
# G5 判分深度诊断
set -u
echo "==================== 1) qwen 容器内 verifier 状态 ===================="
QC=$(docker ps -q --filter "name=qwen38max-152v4" 2>/dev/null | head -1)
if [ -n "$QC" ]; then
  echo "  容器 $QC"
  docker exec "$QC" bash -c '
    echo "  --- /logs/verifier ---"
    ls -la /logs/verifier 2>/dev/null | head -12
    echo "  --- graded 目录 ---"
    ls -la /logs/verifier/graded 2>/dev/null | head -14
    echo "  --- test-stdout 尾部 ---"
    tail -12 /logs/verifier/test-stdout.txt 2>/dev/null
    echo "  --- 容器内进程 ---"
    ps aux | grep -E "test.sh|claude|finalize|python" | grep -v grep | head -8 | cut -c1-130
  ' 2>&1 | head -50
else
  echo "  (qwen 容器不在)"
fi

echo
echo "==================== 2) gpt 容器内 verifier 状态 ===================="
GC=$(docker ps -q --filter "name=gpt56sol-152v4" 2>/dev/null | head -1)
if [ -n "$GC" ]; then
  echo "  容器 $GC"
  docker exec "$GC" bash -c '
    echo "  --- /logs/verifier ---"
    ls -la /logs/verifier 2>/dev/null | head -12
    echo "  --- graded ---"
    ls -la /logs/verifier/graded 2>/dev/null | head -14
    echo "  --- test-stdout 尾部 ---"
    tail -12 /logs/verifier/test-stdout.txt 2>/dev/null
    echo "  --- 容器内进程 ---"
    ps aux | grep -E "test.sh|claude|finalize|python|compose" | grep -v grep | head -8 | cut -c1-130
  ' 2>&1 | head -50
else
  echo "  (gpt 容器不在)"
fi

echo
echo "==================== 3) 两侧宿主 verifier 目录（挂载同步？）===================="
for d in g5-152v4-qwen/trials/qwen38max-152v4 g5-152v4-gpt/trials/gpt56sol-152v4; do
  V=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/$d/verifier
  echo "  --- $d ---"
  find "$V" -type f 2>/dev/null | head -12 | while read -r f; do
    printf '    %-56s %9s  %s\n' "${f#$V/}" "$(stat -c%s "$f")" "$(stat -c%y "$f" | cut -c12-19)"
  done
done

echo
echo "==================== 4) harbor 主进程栈（判断在等什么）===================="
for p in $(pgrep -f "harbor trial start" 2>/dev/null); do
  echo "  PID $p:"
  cat /proc/$p/wchan 2>/dev/null; echo ""
  ls -l /proc/$p/fd 2>/dev/null | grep -E "socket|pipe" | head -3
done
echo "  --- 近 5 分钟 dockerd 日志 ---"
journalctl -u docker --since "5 minutes ago" --no-pager 2>/dev/null | tail -6

echo
echo "DIAG-DONE $(date '+%F %T')"
