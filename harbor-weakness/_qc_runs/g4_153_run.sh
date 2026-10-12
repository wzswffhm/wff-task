#!/bin/bash
# G4 oracle 预检（FIN3-WKN-153）——WSL root 运行，systemd unit 托管。
set -u

# --- WSL 出站走 Windows 侧 pproxy ---
GW=$(ip route 2>/dev/null | sed -n 's/^default via \([0-9.]*\).*/\1/p')
if [ -n "${GW:-}" ]; then
  export http_proxy="http://$GW:18080" https_proxy="http://$GW:18080"
  export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
  export no_proxy="localhost,127.0.0.1,::1"
fi

CREDS=/mnt/c/Users/Administrator/.wff-creds
TASK_ROOT=/mnt/c/Users/Administrator/Desktop/wff-task
OUT=$TASK_ROOT/harbor-weakness/_qc_runs/g4-153
mkdir -p "$OUT/trials"
rm -rf "${OUT:?}/trials"/* 2>/dev/null || true

# shellcheck disable=SC1091
set -a; . "$CREDS/judge.env"; set +a

[ -d /home/wff ] || mkdir -p /home/wff
export HOME=/home/wff
export LANG=C
export PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONUTF8=1

cd "$TASK_ROOT" || exit 90
{
  echo "=== start $(date '+%F %T') ==="
  echo "harbor: $(command -v harbor) $(harbor --version 2>&1 | head -1)"
  echo "proxy: ${https_proxy:-none}"
} > "$OUT/oracle.log"

harbor trial start \
  -p harbor-weakness/work_fin-b01_20261012-153/FIN3-WKN-153 \
  -a oracle \
  --trial-name oracle-153 \
  --trials-dir "$OUT/trials" \
  --ve JUDGE_API_KEY="$JUDGE_API_KEY" \
  --ve JUDGE_BASE_URL="$JUDGE_BASE_URL" \
  --ve JUDGE_MODEL="$JUDGE_MODEL" \
  --ve JUDGE_PROVIDER="$JUDGE_PROVIDER" \
  --ve JUDGE_API_PROTOCOL="$JUDGE_API_PROTOCOL" >> "$OUT/oracle.log" 2>&1
rc=$?
echo "EXIT=$rc" >> "$OUT/oracle.log"
echo "=== done $(date '+%F %T') ===" >> "$OUT/oracle.log"
exit $rc
