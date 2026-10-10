#!/bin/bash
# gpt 容器诊断（不吞错误）
set -u
echo "======== 1) docker ps 全量 ========"
docker ps -a --format '  {{.Names}} | {{.Status}} | {{.Image}}' | head -8

echo
echo "======== 2) gpt 容器内进程（显式报错）========="
GC=$(docker ps -q --filter "name=gpt56sol-152v4" | head -1)
echo "  容器ID: ${GC:-空}"
if [ -n "$GC" ]; then
  docker exec "$GC" ps aux 2>&1 | head -16 | sed 's/^/    /'
  echo "  --- test.sh/rewardkit/claude ---"
  docker exec "$GC" bash -c 'ps aux | grep -vE "grep|ps aux" | grep -E "test|reward|claude|finalize|python" | head -8' 2>&1 | sed 's/^/    /'
fi

echo
echo "======== 3) gpt /logs/verifier 详情 ========"
if [ -n "$GC" ]; then
  docker exec "$GC" bash -c 'ls -la /logs/verifier/ 2>&1; echo "--- graded ---"; ls -la /logs/verifier/graded/ 2>&1; echo "--- stdout ---"; wc -c /logs/verifier/test-stdout.txt 2>&1; echo "--- 最近修改 ---"; find /logs -type f -mmin -15 2>/dev/null | head -10' 2>&1 | sed 's/^/    /'
fi

echo
echo "======== 4) gpt 宿主侧 trial.log 全文尾部 ========"
T=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g5-152v4-gpt/trials/gpt56sol-152v4
tail -6 "$T/trial.log" 2>/dev/null | sed 's/^/    /'
echo "    trial.log 大小: $(stat -c%s "$T/trial.log" 2>/dev/null)"

echo
echo "======== 5) harbor 主进程（还剩几个）========="
ps aux | grep "harbor trial start" | grep -v grep | awk '{print "    PID", $2, "start", $9}' | head -4

echo
echo "======== 6) opus 进度对照 ========"
OT=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g5-152v4-opus/trials/opus48-152v4
find "$OT" -type f -newermt "-8 minutes" 2>/dev/null | head -6 | while read -r f; do
  printf '    %-56s %9s %s\n' "${f#$OT/}" "$(stat -c%s "$f")" "$(stat -c%y "$f" | cut -c12-19)"
done
OC=$(docker ps -q --filter "name=opus48-152v4" | head -1)
[ -n "$OC" ] && docker exec "$OC" bash -c 'ps aux | grep -vE "grep" | grep -E "rewardkit|claude -p|test.sh" | head -4 | cut -c1-105' 2>&1 | sed 's/^/    /'

echo
echo "DIAG-DONE $(date '+%F %T')"
