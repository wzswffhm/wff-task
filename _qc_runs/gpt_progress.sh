#!/bin/bash
# gpt 判分进度
echo "======== 1) gpt 容器内进程 ========"
GC=$(docker ps -q --filter "name=gpt56sol-152v4" 2>/dev/null | head -1)
if [ -n "$GC" ]; then
  echo "  容器 $GC $(docker ps --filter id=$GC --format '{{.Status}}')"
  docker exec "$GC" bash -c '
    echo "  --- rewardkit/判官进程 ---"
    ps aux | grep -E "rewardkit|claude -p|test.sh|finalize" | grep -v grep | head -6 | cut -c1-120
    echo "  --- /logs/verifier/graded ---"
    ls -la /logs/verifier/graded 2>/dev/null | head -12
    echo "  --- 临时判分产物（rewardkit 工作目录）---"
    find /tmp /logs -name "*reward*" -o -name "*graded*" -o -name "*criteria*" 2>/dev/null | head -12
    echo "  --- test-stdout ---"
    wc -c /logs/verifier/test-stdout.txt 2>/dev/null
  ' 2>&1 | head -40
else
  echo "  (gpt 容器不在 → 可能已完成或已销毁)"
fi

echo
echo "======== 2) harbor trial 主进程 ========"
ps aux | grep "harbor trial start" | grep -v grep | awk '{print "  PID", $2, "启动", $9, $10}' | head -4
n=$(pgrep -cf "harbor trial start" 2>/dev/null || echo 0)
echo "  进程数: $n"

echo
echo "======== 3) gpt trial.log 尾部 ========"
tail -8 /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g5-152v4-gpt/trials/gpt56sol-152v4/trial.log 2>/dev/null | sed 's/^/  /'

echo
echo "======== 4) qwen trial.log 尾部（对照已完成的样子）========="
tail -5 /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g5-152v4-qwen/trials/qwen38max-152v4/trial.log 2>/dev/null | sed 's/^/  /'

echo
echo "PROGRESS-DONE $(date '+%F %T')"
