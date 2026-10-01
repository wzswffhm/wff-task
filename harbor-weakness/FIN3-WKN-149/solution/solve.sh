#!/bin/bash
# FIN3-WKN-149 Oracle 入口：生成参考答案到 /app/output（正向预检基准）。
set -euo pipefail
mkdir -p /app/output

REPRO=/solution/golden_output/FIN3-WKN-149_reproduce.py
if [ -f "$REPRO" ] && python3 "$REPRO" /app/input_files /app/output; then
  # 可复算代码本身也是必交交付物之一，必须一并落到 /app/output
  cp "$REPRO" /app/output/
  echo "[solve.sh] 已由 reproduce.py 从 input_files 原始快照复算生成交付物"
else
  echo "[solve.sh] 复算不可用，回退为直接复制参考答案" >&2
  cp -R /solution/golden_output/. /app/output/
fi

echo "[solve.sh] 交付物清单："
find /app/output -type f | sort
