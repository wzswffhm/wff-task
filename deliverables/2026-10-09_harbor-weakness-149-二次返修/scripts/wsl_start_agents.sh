#!/usr/bin/env bash
# 启动 FIN3-WKN-149 fix8 的三个候选执行体（qwen / gpt / opus），彼此独立、分离于当前会话
set -u
RUNDIR=/home/wff/harbor-runs/FIN3-WKN-149-fix8
CFGDIR=/mnt/c/Users/Administrator/.wff-creds/fin149_fix8_configs
cd /home/wff || exit 1

for m in qwen gpt opus; do
  setsid nohup /home/wff/.local/bin/harbor trial start -c "$CFGDIR/$m.json" > "$RUNDIR/$m.out" 2>&1 < /dev/null &
  echo "started $m pid=$!"
  sleep 6
done

sleep 12
echo "=== running trials ==="
ps -eo pid,user,etime,cmd | grep 'fin149_fix8_configs' | grep -v grep
