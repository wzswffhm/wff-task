#!/usr/bin/env bash
# fix8 综合状态：容器 / 判分结果 / 轨迹轮数 / 产物
set -u
R=/home/wff/harbor-runs/FIN3-WKN-149-fix8

echo "时间: $(date '+%F %T')"
echo
echo "########## 容器 ##########"
docker ps --format '{{.Names}}\t{{.Status}}'
echo
echo "########## 判分结果 ##########"
for t in "$R"/trials-oracle/*/ "$R"/trials-qwen/*/ "$R"/trials-gpt/*/ "$R"/trials-opus/*/; do
  [ -d "$t" ] || continue
  n=$(basename "$t")
  rj="$t/verifier/reward.json"
  em="$t/verifier/reward_exit_message.json"
  if [ -f "$rj" ]; then
    if [ -f "$em" ]; then
      echo "  $n  [未完成/占位]  $(tr -d '\n' < "$rj")"
    else
      echo "  $n  [有效]  $(tr -d '\n' < "$rj")"
    fi
  else
    echo "  $n  [无 reward.json]"
  fi
done
echo "  opus旧轮重判: $(tr -d '\n' < "$R/rejudge-opus/logs/verifier/reward.json" 2>/dev/null)"
echo
echo "########## 轨迹轮数（assistant 事件数） ##########"
for f in "$R"/trials-qwen/*/agent/claude-code.txt "$R"/trials-gpt/*/agent/claude-code.txt \
         "$R"/trials-opus/*/agent/claude-code.txt; do
  [ -f "$f" ] || continue
  printf '  %-58s %6s 轮  %10s B  %s\n' "$(echo "$f" | sed "s|$R/||")" \
    "$(grep -c assistant "$f")" "$(stat -c%s "$f")" "$(stat -c%y "$f" | cut -d. -f1)"
done
echo
echo "########## 当前容器内 /app/output ##########"
for c in $(docker ps --format '{{.Names}}' | grep -E '149__' | sort); do
  echo "--- $c"
  docker exec "$c" find /app/output -type f -printf '%10s %f\n' 2>/dev/null | sort -k2
done
echo
echo "########## opus 重判进度 ##########"
docker exec fin149-opus-rejudge ps -eo etime,pcpu,comm 2>/dev/null | head -5
