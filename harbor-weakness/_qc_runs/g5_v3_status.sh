#!/bin/bash
# G5 v3 进度：含 agent 阶段 todo 进度（第 N/M 个）
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

# 解析某模型的 agent todo：返回 "done/total|cur"
agent_todos() {  # $1 = trial 目录 glob 基路径
  f=$(find "$1" -name claude-code.txt 2>/dev/null | head -1)
  [ -f "$f" ] || { echo "-/-|"; return; }
  python3 - "$f" <<'PY'
import json, sys
todos = []
for line in open(sys.argv[1], encoding="utf-8", errors="ignore"):
    line = line.strip()
    if not line.startswith("{"): continue
    try: d = json.loads(line)
    except Exception: continue
    for c in ((d.get("message") or {}).get("content") or []):
        if isinstance(c, dict) and c.get("name") == "TodoWrite" and c.get("type") == "tool_use":
            todos = (c.get("input") or {}).get("todos") or []
if todos:
    done = sum(1 for t in todos if t.get("status") == "completed")
    cur = next(((t.get("activeForm") or t.get("content") or "")[:26] for t in todos
                if t.get("status") == "in_progress"), "")
    print(f"{done}/{len(todos)}|{cur}")
else:
    print("-/-|")
PY
}

# 判分进度：返回 "第N/37(Rxx)"——宽松匹配判官进程命令行里的 Rxx/Nxx
judge_prog() {  # $1 = 容器名
  line=$(docker exec "$1" sh -c "ps -eo etimes,args --no-headers | grep 'claude -p' | grep -v grep | head -1" 2>/dev/null)
  [ -n "${line:-}" ] || { echo "-"; return; }
  cid=$(echo "$line" | grep -oE "[RN][0-9]{2}" | head -1)
  [ -n "${cid:-}" ] || { echo "判分中"; return; }
  case "$cid" in
    R*) idx=$(( 10#${cid#R} )) ;;
    N*) idx=$(( 29 + 10#${cid#N} )) ;;
    *) idx="?" ;;
  esac
  echo "第${idx}/37(${cid})"
}

TOTAL=37
echo "=== v3 进度快照 $(date '+%F %T')  总判据 ${TOTAL} ==="
printf '%-18s|%-8s|%-22s|%-14s|%s\n' "场次" "阶段" "agent进度" "判据进度" "得分/产物"
for spec in \
  "oracle:v3:oracle-152v3__env-main-1:g4-152v3" \
  "qwen3.8-max-0902:v3:qwen38max-152v3__env-main-1:g5-152v3-qwen" \
  "gpt-5.6-sol:v3:gpt56sol-152v3__env-main-1:g5-152v3-gpt" ; do
  label="${spec%%:*}"; r1="${spec#*:}"; ver="${r1%%:*}"; r2="${r1#*:}"
  c="${r2%%:*}"; dir="${r2##*:}"; rw=""

  rj=$(find "$Q/$dir/trials" -maxdepth 3 -name reward.json 2>/dev/null | head -1)
  if [ -n "$rj" ]; then
    ve=$(sed -n 's/.*"verifier_error": *\([0-9.]*\).*/\1/p' "$rj")
    rw=$(sed -n 's/.*"reward": *\([0-9.]*\).*/\1/p' "$rj")
    if [ "${ve%.*}" = "0" ]; then
      printf '%-18s|%-8s|%-22s|%-14s|%s\n' "$label $ver" "完成" "37/37" "37/37" "$rw"
      continue
    fi
  fi
  if ! docker ps --format '{{.Names}}' | grep -qx "$c"; then
    printf '%-18s|%-8s|%-22s|%-14s|%s\n' "$label $ver" "已结束" "-" "-" "${rw:-?}"
    continue
  fi
  jt=$(judge_prog "$c")
  if [ "$jt" != "-" ]; then
    printf '%-18s|%-8s|%-22s|%-14s|%s\n' "$label $ver" "判分" "-" "$jt" "-"
  else
    ag=$(agent_todos "$Q/$dir/trials")
    ad="${ag%%|*}"; ac="${ag##*|}"
    out=$(docker exec "$c" sh -c 'ls /app/output 2>/dev/null | wc -l' 2>/dev/null)
    printf '%-18s|%-8s|%-22s|%-14s|%s\n' "$label $ver" "agent" "${ad} ${ac:-}" "未开判" "产物${out}"
  fi
done
