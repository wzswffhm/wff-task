#!/usr/bin/env bash
set -u
R=/home/wff/harbor-runs/FIN3-WKN-149-fix8
echo "=== 全部试次目录及归属 ==="
for d in "$R"/trials-*/; do
  for t in "$d"FIN3-WKN-149__*/; do
    [ -d "$t" ] || continue
    n=$(basename "$t")
    st="无 reward"
    [ -f "$t/verifier/reward.json" ] && st="有 reward"
    [ -f "$t/verifier/reward_exit_message.json" ] && st="占位(未完成)"
    printf '  %-22s %-26s %-16s %s\n' "$(basename "$d")" "$n" "$st" "$(stat -c%y "$t" | cut -d. -f1)"
  done
done
echo
echo "=== hzH6CWS 定位 ==="
find "$R" -maxdepth 2 -name '*hzH6CWS*' 2>/dev/null
echo
echo "=== 判分进程 ==="
ps -eo etime,cmd | grep 'test.sh' | grep -v grep | sed 's/\(--project-name [^ ]*\).*/\1/' | head -10
