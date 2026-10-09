#!/bin/bash
# FIN3-WKN-152 判据级进度 v2
# 关键：reward.json 可能是 rewardkit 的 fail-closed 占位符（verifier_error=1），
#       只要对应 service 仍 active，就说明判分还在跑，不能当已完成。
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
TOTAL=33

snapshot() {
  printf '%-20s %-8s %-18s %-10s %s\n' "场次" "阶段" "判据进度" "当前判据" "备注"
  for spec in \
    "gpt56sol4-152v2__env-main-1:gpt-5.6-sol:g5-152v2-gpt4:g5-gpt-152v2.service" \
    "qwen38max2-152v2__env-main-1:qwen3.8-max-0902:g5-152v2-qwen2:g5-qwen-152v2.service" ; do

    c="${spec%%:*}"; r1="${spec#*:}"; label="${r1%%:*}"; r2="${r1#*:}"
    dir="${r2%%:*}"; svc="${r2##*:}"

    live=$(systemctl is-active "$svc" 2>/dev/null)

    if [ "$live" != "active" ]; then
      rj=$(find "$R/$dir/trials" -maxdepth 3 -name reward.json 2>/dev/null | head -1)
      if [ -n "$rj" ]; then
        cc=$(sed -n 's/.*"criteria_counted": *\([0-9.]*\).*/\1/p' "$rj")
        rw=$(sed -n 's/.*"reward": *\([0-9.]*\).*/\1/p' "$rj")
        ve=$(sed -n 's/.*"verifier_error": *\([0-9.]*\).*/\1/p' "$rj")
        printf '%-20s %-8s %-18s %-10s %s\n' "$label" "已结束" "${cc:-?}/$TOTAL" "—" "reward=${rw:-?} verifier_error=${ve:-?}"
      else
        printf '%-20s %-8s %-18s %-10s %s\n' "$label" "已结束" "—" "—" "无 reward.json"
      fi
      continue
    fi

    if ! docker ps --format '{{.Names}}' | grep -qx "$c"; then
      printf '%-20s %-8s %-18s %-10s %s\n' "$label" "构建/收尾" "—" "—" "容器暂不可见"
      continue
    fi

    is_agent=$(docker exec "$c" sh -c "ps -eo args --no-headers 2>/dev/null | grep -c 'claude --verbose'" 2>/dev/null)
    cur=$(docker exec "$c" sh -c "ps -eo etimes,args --no-headers 2>/dev/null | grep 'claude -p' | grep -v grep | head -1" 2>/dev/null)
    cid=$(printf '%s' "$cur" | grep -oE "\\- '[A-Z][0-9][0-9]'" | tail -1 | sed "s/[- ']//g")
    age=$(printf '%s' "$cur" | awk '{print $1}')

    idx=""
    if [ -n "${cid:-}" ]; then
      case "$cid" in
        R*) idx=$(( 10#${cid#R} )) ;;
        N*) idx=$(( 29 + 10#${cid#N} )) ;;
      esac
    fi

    if [ -n "${cid:-}" ]; then
      prod=$(docker exec "$c" sh -c 'ls /app/output 2>/dev/null | wc -l' 2>/dev/null)
      printf '%-20s %-8s %-18s %-10s %s\n' "$label" "判分" "第 ${idx:-?}/$TOTAL 条" "$cid" "耗时=${age:-?}s 产物=${prod:-?}"
    elif [ "${is_agent:-0}" -ge 1 ] 2>/dev/null; then
      traj=$(docker exec "$c" sh -c 'wc -c < /logs/agent/claude-code.txt' 2>/dev/null)
      prod=$(docker exec "$c" sh -c 'ls /app/output 2>/dev/null | wc -l' 2>/dev/null)
      printf '%-20s %-8s %-18s %-10s %s\n' "$label" "agent" "0/$TOTAL（未开判）" "—" "轨迹=${traj:-?}B 产物=${prod:-?}"
    else
      printf '%-20s %-8s %-18s %-10s %s\n' "$label" "判分/收尾" "—" "—" "等待判据进程"
    fi
  done
}

echo "=== 判据进度快照 $(date '+%F %T')  总判据 ${TOTAL} ==="
snapshot
