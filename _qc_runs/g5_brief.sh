#!/bin/bash
# 精简进度：只看判官进程身份（PID/启动时间/当前判据）与 reward 状态
echo "=== $(date '+%F %T') ==="
for c in gpt56sol-152v4 opus48-152v4 qwen38max-152v4; do
  CID=$(docker ps -q --filter "name=$c" | head -1)
  if [ -z "$CID" ]; then
    echo "[$c] (容器不在)"
    continue
  fi
  echo "[$c]"
  # 判官进程：PID、启动(容器UTC)、CPU累计、当前判据ID
  docker exec "$CID" bash -c '
    p=$(pgrep -f "claude -p You are an evaluation judge" | head -1)
    if [ -z "$p" ]; then echo "    判官: 无（阶段间隙或已完成）"; else
      start=$(ps -o lstart= -p "$p" 2>/dev/null)
      cpu=$(ps -o cputimes= -p "$p" 2>/dev/null | tr -d " ")
      cur=$(tr "\0" " " < /proc/$p/cmdline 2>/dev/null | grep -oE "\x27R[0-9]+\x27|\x27N0[0-9]\x27" | head -1)
      echo "    判官 PID=$p 启动=$start CPU=${cpu}s 当前判据=$cur"
    fi
    rk=$(pgrep -f "rewardkit /tests" | head -1)
    echo "    rewardkit PID=${rk:-无}"
  ' 2>&1 | sed 's/^/  /'
  # reward / details
  T=$(ls -d /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/*/trials/"$c" 2>/dev/null | head -1)
  if [ -n "$T" ] && [ -f "$T/verifier/reward.json" ]; then
    echo "    reward: $(tr -d "\n" < "$T/verifier/reward.json" | head -c 120)"
    [ -f "$T/verifier/graded/reward-details.json" ] && echo "    details: $(stat -c%s "$T/verifier/graded/reward-details.json") B ✓"
  fi
done

echo
echo "--- 宿主侧 trial.log 是否推进（尾行时间）---"
for f in /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g5-152v4-gpt/trials/gpt56sol-152v4/trial.log \
         /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g5-152v4-opus/trials/opus48-152v4/trial.log; do
  [ -f "$f" ] && echo "  $(basename $(dirname $(dirname $f))): size=$(stat -c%s "$f") mtime=$(stat -c%y "$f" | cut -c12-19)"
done
