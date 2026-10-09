#!/usr/bin/env bash
# 详细跑分进度：容器侧（模型识别 + /app/output 产物）与宿主机侧（轨迹轮数/工具调用/末尾动作）
set -u
RUNDIR=/home/wff/harbor-runs/FIN3-WKN-149-fix8

echo "################ 容器侧 ################"
for c in $(docker ps --format '{{.Names}}' | grep '149__' | sort); do
  echo "########## $c"
  docker exec "$c" env 2>/dev/null | grep -E '^(ANTHROPIC_BASE_URL|ANTHROPIC_MODEL)=' || true
  echo "-- /app/output 产物 --"
  docker exec "$c" find /app/output -type f -printf '%10s  %p\n' 2>/dev/null | sort -k2 || true
  echo "-- 容器内进程 --"
  docker exec "$c" ps -eo etime,pcpu,comm --sort=-pcpu 2>/dev/null | head -6 || true
  echo
done

echo "################ 宿主机侧轨迹 ################"
for d in "$RUNDIR"/trials-qwen/*/ "$RUNDIR"/trials-gpt/*/ "$RUNDIR"/trials-opus/*/; do
  f="$d/agent/claude-code.txt"
  [ -f "$f" ] || continue
  echo "----- $d"
  echo "size=$(stat -c%s "$f") bytes  lines=$(wc -l < "$f")  mtime=$(stat -c%y "$f" | cut -d. -f1)"
  echo -n "assistant(轮)="; grep -c '"type":"assistant"' "$f" 2>/dev/null || echo 0
  echo -n "tool_use(次)="; grep -o '"type":"tool_use"' "$f" 2>/dev/null | wc -l
  echo -n "result(收尾)="; grep -c '"type":"result"' "$f" 2>/dev/null || echo 0
  echo "最近 5 个工具调用名:"; grep -o '"name":"[A-Za-z_]*"' "$f" 2>/dev/null | tail -5
  echo "末尾 3 行(截断):"; tail -3 "$f" | cut -c1-220
  echo
done

echo "################ trial 目录状态 ################"
for t in "$RUNDIR"/trials-qwen/*/ "$RUNDIR"/trials-gpt/*/ "$RUNDIR"/trials-opus/*/; do
  echo "$t : $(ls "$t" 2>/dev/null | tr '\n' ' ')"
done
