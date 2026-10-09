#!/usr/bin/env bash
# 重跑 opus 执行体（新试次），保留旧轮 6AB4Ng8 的产物与轨迹作为证据
set -u
RUNDIR=/home/wff/harbor-runs/FIN3-WKN-149-fix8
CFGDIR=/mnt/c/Users/Administrator/.wff-creds/fin149_fix8_configs
export DOCKER_CONFIG=/home/wff/.docker-fix8

cd /home/wff || exit 1
before=$(ls -d "$RUNDIR"/trials-opus/*/ 2>/dev/null | wc -l)
echo "重跑前 trials-opus 试次数: $before"
setsid nohup env DOCKER_CONFIG="$DOCKER_CONFIG" /home/wff/.local/bin/harbor trial start \
  -c "$CFGDIR/opus.json" > "$RUNDIR/opus_rerun.out" 2>&1 < /dev/null &
echo "started opus rerun pid=$!"
sleep 25
echo "=== 进程 ==="
ps -eo pid,user,etime,cmd | grep 'fin149_fix8_configs/opus.json' | grep -v grep
echo "=== 日志 ==="
tail -n 5 "$RUNDIR/opus_rerun.out"
echo "=== 试次数 ==="
ls -d "$RUNDIR"/trials-opus/*/ 2>/dev/null
