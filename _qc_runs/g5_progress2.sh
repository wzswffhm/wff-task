#!/bin/bash
# G5 gpt/opus 进度
echo "======== 1) 容器 ========"
docker ps --format '  {{.Names}} | {{.Status}}' | head -6

echo
echo "======== 2) 各容器关键进程 ========"
for c in gpt56sol-152v4 opus48-152v4; do
  echo "  [$c]"
  if docker ps -q --filter "name=$c" | grep -q .; then
    docker exec "$c" bash -c 'ps aux | grep -E "rewardkit|claude -p|test.sh|claude-code" | grep -v grep | head -4 | cut -c1-115' 2>/dev/null | sed 's/^/    /'
  else
    echo "    (无容器)"
  fi
done

echo
echo "======== 3) 宿主 trial 关键文件 ========"
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
for pair in "g5-152v4-gpt/trials/gpt56sol-152v4:gpt" "g5-152v4-opus/trials/opus48-152v4:opus"; do
  d="${pair%%:*}"; n="${pair##*:}"
  T=$Q/$d
  echo "  [$n] $d"
  if [ -d "$T" ]; then
    find "$T" -type f -newermt "-10 minutes" 2>/dev/null | head -6 | while read -r f; do
      printf '    %-58s %9s  %s\n' "${f#$T/}" "$(stat -c%s "$f")" "$(stat -c%y "$f" | cut -c12-19)"
    done
    r=$T/verifier/reward.json
    if [ -f "$r" ]; then
      echo "    >>> reward.json: $(tr -d '\n' < "$r")"
    else
      echo "    reward.json: 未生成"
    fi
    out=$T/artifacts/app/output
    [ -d "$out" ] && echo "    交付物: $(ls "$out" 2>/dev/null | wc -l) 个"
    tl=$T/trial.log
    [ -s "$tl" ] && echo "    trial.log 尾1行: $(tail -1 "$tl" | cut -c1-100)"
  else
    echo "    (trial 目录未建)"
  fi
done

echo
echo "PROG-DONE $(date '+%F %T')"
