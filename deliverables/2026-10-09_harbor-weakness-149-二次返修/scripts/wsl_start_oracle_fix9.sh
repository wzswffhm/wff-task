#!/usr/bin/env bash
# 把 fix9 oracle config 传到 WSL 并启动 oracle 重跑（隔离 DOCKER_CONFIG 规避 buildx 权限）
set -e
export PATH="$PATH:/home/wff/.local/bin"
export DOCKER_CONFIG=/home/wff/.docker-fix8
CFG_WIN="/mnt/c/Users/Administrator/.wff-creds/fin149_fix9_configs/oracle.json"
CFG_WSL="/home/wff/.wff-creds-fix9/oracle.json"
mkdir -p /home/wff/.wff-creds-fix9
cp "$CFG_WIN" "$CFG_WSL"
chmod 600 "$CFG_WSL"
echo "=== config 就位（DOCKER_CONFIG=$DOCKER_CONFIG）==="
echo "=== 启动 oracle trial start ==="
mkdir -p /home/wff/harbor-runs/FIN3-WKN-149-fix9/trials-oracle
cd /home/wff
harbor trial start -c "$CFG_WSL" > /home/wff/harbor-runs/FIN3-WKN-149-fix9/oracle_fix9.out 2>&1 &
echo "oracle 启动 pid=$!"
sleep 8
echo "=== 前 40 行输出 ==="
head -40 /home/wff/harbor-runs/FIN3-WKN-149-fix9/oracle_fix9.out 2>/dev/null || echo "(尚无输出)"
