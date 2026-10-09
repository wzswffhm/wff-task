#!/bin/bash
# 跑分状态巡检（含 gpt 三次试次）
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

echo "=== units ==="
for u in g4-152v2 g5-gpt-152v2 g5-gpt2-152v2 g5-gpt3-152v2 g5-pipeline; do
  printf '%-18s %s\n' "$u" "$(systemctl is-active "$u" 2>&1)"
done

echo
echo "=== rewards ==="
for d in g4-152v2 g5-152v2-gpt g5-152v2-gpt2 g5-152v2-gpt3 g5-152v2-qwen; do
  f=$(find "$R/$d/trials" -maxdepth 3 -name reward.json 2>/dev/null | head -1)
  if [ -n "$f" ]; then
    printf '%-18s %s\n' "$d" "$(tr -d '\n' < "$f")"
  else
    printf '%-18s (尚无 reward.json)\n' "$d"
  fi
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
      printf '%-34s 轨迹=%sB  产物=%s\n' "$c" "${b:-?}" "${n:-?}"
      ;;
  esac
done

echo
echo "=== pipeline log tail ==="
tail -3 "$R/g5_pipeline.log"
