#!/usr/bin/env bash
# 启动 fix10 oracle 重跑（真实同源七件套：WSL 任务目录金标已补齐新图）
set -e
export PATH="$PATH:/home/wff/.local/bin"
export DOCKER_CONFIG=/home/wff/.docker-fix8
CFG_WIN="/mnt/c/Users/Administrator/.wff-creds/fin149_fix10_configs/oracle.json"
CFG_WSL="/home/wff/.wff-creds-fix10/oracle.json"
mkdir -p /home/wff/.wff-creds-fix10
cp "$CFG_WIN" "$CFG_WSL"
chmod 600 "$CFG_WSL"
mkdir -p /home/wff/harbor-runs/FIN3-WKN-149-fix10/trials-oracle
echo "=== 确认 WSL 金标图已是新图 ==="
sha256sum /home/wff/harbor-tasks-fix8/FIN3-WKN-149/solution/golden_output/FIN3-WKN-149_charts/*.png | cut -c1-16
echo "=== 启动 oracle trial start ==="
cd /home/wff
setsid nohup env DOCKER_CONFIG="$DOCKER_CONFIG" /home/wff/.local/bin/harbor trial start -c "$CFG_WSL" \
  > /home/wff/harbor-runs/FIN3-WKN-149-fix10/oracle.out 2>&1 < /dev/null &
echo "pid=$!"
sleep 20
echo "=== 输出 ==="
tail -12 /home/wff/harbor-runs/FIN3-WKN-149-fix10/oracle.out
