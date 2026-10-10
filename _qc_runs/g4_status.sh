#!/bin/bash
# 查询 G4 oracle-152v4 运行阶段
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g4-152v4
T=$Q/trials/oracle-152v4

echo "======== 1) 容器 ========"
docker ps --format '  {{.Names}} | {{.Status}} | {{.Image}}' 2>/dev/null | head -5

echo
echo "======== 2) 关键进程 ========"
ps aux | grep -E "harbor trial|docker compose|docker-compose|claude|solve\.sh|test\.sh|finalize" | grep -v grep | head -8 | cut -c1-160

echo
echo "======== 3) trial 目录（按时间）========"
find "$T" -type f 2>/dev/null | head -30 | while read -r f; do
  printf '  %-62s %10s  %s\n' "${f#$T/}" "$(stat -c%s "$f" 2>/dev/null)" "$(stat -c%y "$f" 2>/dev/null | cut -c12-19)"
done

echo
echo "======== 4) 容器内 /app/output 与 verifier 状态 ========"
CID=$(docker ps -q --filter "name=oracle" 2>/dev/null | head -1)
if [ -n "$CID" ]; then
  echo "  容器: $CID"
  docker exec "$CID" bash -c 'echo "  /app/output:"; ls -la /app/output 2>/dev/null | head -10; echo "  /tests:"; ls /tests 2>/dev/null | head -8' 2>&1 | head -22
else
  echo "  (无 oracle 容器在跑)"
fi

echo
echo "======== 5) harbor trial 日志（trial.log 若有内容）========"
if [ -s "$T/trial.log" ]; then
  tail -20 "$T/trial.log" | sed 's/^/  /'
else
  echo "  trial.log 仍为空（0 B）"
fi

echo
echo "======== 6) 挂载的日志（verifier 是否开始）========"
find "$T/verifier" -type f 2>/dev/null | head -10 | while read -r f; do
  printf '  %-55s %10s\n' "${f#$T/}" "$(stat -c%s "$f")"
done
[ -d "$T/verifier" ] || echo "  (verifier 目录尚未创建 → 仍在 agent/环境阶段)"

echo
echo "G4-STATUS-DONE $(date '+%F %T')"
