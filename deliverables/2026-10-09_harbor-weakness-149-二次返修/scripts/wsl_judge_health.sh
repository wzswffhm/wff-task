#!/usr/bin/env bash
set -u
Q=fin3-wkn-149__uqnx7ti__env-main-1
G=fin3-wkn-149__qsfcmtd__env-main-1
O=fin3-wkn-149__vtphqtw__env-main-1
R=/home/wff/harbor-runs/FIN3-WKN-149-fix8

for pair in "qwen:$Q:$R/trials-qwen/FIN3-WKN-149__uqNx7ti" \
            "gpt:$G:$R/trials-gpt/FIN3-WKN-149__qsFcMtD" \
            "opus:$O:$R/trials-opus/FIN3-WKN-149__vTPHQTW"; do
  m=${pair%%:*}; rest=${pair#*:}; c=${rest%%:*}; t=${rest#*:}
  echo "########## $m  ($c)"
  echo -n "  claude judge 进程数: "
  docker exec "$c" ps aux 2>/dev/null | grep -c '[c]laude -p' || true
  echo "  当前/最近判据（etime | 判据号）:"
  docker exec "$c" ps -eo etime,cmd 2>/dev/null | grep '[c]laude -p' \
    | sed -E "s/^ *([0-9:]+).*- '([A-Z0-9]+)'.*/    \1   \2/" | tail -3
  echo -n "  rewardkit 运行时长/CPU: "
  docker exec "$c" ps -eo etime,pcpu,comm 2>/dev/null | grep '[r]ewardkit' | head -1
  echo -n "  graded 目录: "
  docker exec "$c" ls -l /logs/verifier/graded/ 2>/dev/null | tail -n +2 | awk '{printf "%s(%s) ", $9, $5}'
  echo
  echo -n "  本机 verifier: "
  if [ -f "$t/verifier/reward_exit_message.json" ]; then echo "判分中（占位）"; else echo "已出分"; fi
  echo
done

echo "########## 全局判分进程 ##########"
ps -eo etime,cmd | grep '[t]est.sh' | sed -E 's#.*project-name ([^ ]*).*#    \1#' | sort | uniq -c
