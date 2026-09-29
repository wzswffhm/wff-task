#!/bin/bash
# Oracle 入口：将专家标准答案复制到 /app/output
set -euo pipefail
mkdir -p /app/output
SOLUTION_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cp -a "$SOLUTION_DIR/golden_output/." /app/output/
