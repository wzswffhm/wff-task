#!/bin/bash
# 查 systemd journal：unit 为何停止
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

echo "=== journal: g5-pipeline ==="
journalctl -u g5-pipeline --no-pager -n 40 2>&1 | tail -40

echo
echo "=== journal: g5-gpt3-152v2 ==="
journalctl -u g5-gpt3-152v2 --no-pager -n 30 2>&1 | tail -30

echo
echo "=== journal 全局：最近 60 行的 systemd 事件 ==="
journalctl --no-pager -n 60 --since "20:05" 2>&1 | grep -iE 'g5|g4|kill|stop|fail|oom|terminat' | tail -30

echo
echo "=== gpt3 gpt.log 末尾 ==="
tail -12 "$R/g5-152v2-gpt3/gpt.log" 2>/dev/null || echo "(无)"

echo
echo "=== qwen 是否有独立日志 ==="
ls -la "$R"/g5-152v2-qwen/ 2>&1 | head -8
tail -8 "$R/g5_pipeline.log" 2>/dev/null
