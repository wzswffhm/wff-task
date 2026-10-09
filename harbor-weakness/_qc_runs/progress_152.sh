#!/bin/bash
# G5 实时进度（持久 service 版）
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

echo "=== services ==="
for s in g5-qwen-152v2.service g5-gpt-152v2.service; do
  printf '%-26s %s  (since %s)\n' "$s" "$(systemctl is-active "$s")" "$(systemctl show -p ActiveEnterTimestamp --value "$s")"
done

echo
echo "=== containers ==="
docker ps --format '{{.Names}} | {{.Status}}'

echo
echo "=== agent 进度 ==="
for c in $(docker ps --format '{{.Names}}'); do
  case "$c" in
    *env-main-1)
      b=$(docker exec "$c" sh -c 'wc -c < /logs/agent/claude-code.txt 2>/dev/null' 2>/dev/null)
      n=$(docker exec "$c" sh -c 'ls /app/output 2>/dev/null | wc -l' 2>/dev/null)
      p=$(docker exec "$c" sh -c "ps -eo etimes,args --no-headers 2>/dev/null | grep -E 'claude -p|claude --' | grep -v grep | head -1 | awk '{print \$1}'" 2>/dev/null)
      printf '%-34s 轨迹=%sB  产物=%s  进程时长=%ss\n' "$c" "${b:-?}" "${n:-?}" "${p:-?}"
      ;;
  esac
done

echo
echo "=== rewards ==="
for d in g4-152v2 g5-152v2-qwen2 g5-152v2-gpt4; do
  f=$(find "$R/$d/trials" -maxdepth 3 -name reward.json 2>/dev/null | head -1)
  if [ -n "$f" ]; then printf '%-18s %s\n' "$d" "$(tr -d '\n' < "$f")"; else printf '%-18s (尚无)\n' "$d"; fi
done

echo
echo "=== 时间 ==="
date '+%F %T'
