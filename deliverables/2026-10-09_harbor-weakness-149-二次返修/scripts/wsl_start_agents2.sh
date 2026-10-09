#!/usr/bin/env bash
# 重启 fix8 三个候选执行体：显式隔离 DOCKER_CONFIG，避免 152 侧 root 进程写入
# /home/wff/.docker/buildx/current(root 0600) 导致 buildx/bake 读取 permission denied。
set -u
RUNDIR=/home/wff/harbor-runs/FIN3-WKN-149-fix8
CFGDIR=/mnt/c/Users/Administrator/.wff-creds/fin149_fix8_configs

export DOCKER_CONFIG=/home/wff/.docker-fix8
mkdir -p "$DOCKER_CONFIG"
chmod 700 "$DOCKER_CONFIG"

# 清掉可能已退出的同名进程
pkill -f 'fin149_fix8_configs/(qwen|gpt|opus)\.json' 2>/dev/null
sleep 2

echo "DOCKER_CONFIG=$DOCKER_CONFIG"
ls -la "$DOCKER_CONFIG"

cd /home/wff || exit 1
for m in qwen gpt opus; do
  setsid nohup env DOCKER_CONFIG="$DOCKER_CONFIG" /home/wff/.local/bin/harbor trial start \
    -c "$CFGDIR/$m.json" > "$RUNDIR/$m.out" 2>&1 < /dev/null &
  echo "started $m pid=$!"
  sleep 6
done

sleep 20
echo "=== running trials ==="
ps -eo pid,user,etime,cmd | grep 'fin149_fix8_configs' | grep -v grep
echo "=== buildx current ==="
ls -l "$DOCKER_CONFIG/buildx/current" 2>&1
