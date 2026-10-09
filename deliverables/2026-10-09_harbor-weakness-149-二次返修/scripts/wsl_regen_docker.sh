#!/usr/bin/env bash
# 在题目自带镜像 fin3-wkn-149:local 内全流程复算 golden（项7 验收证据）
set -u
PKG=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/FIN3-WKN-149
OUT=/mnt/c/Users/Administrator/Desktop/wff-task/deliverables/2026-10-09_harbor-weakness-149-二次返修/_regen_docker
rm -rf "$OUT"; mkdir -p "$OUT"

echo "=== 镜像 python/依赖 ==="
docker run --rm --entrypoint python3 fin3-wkn-149:local -c \
  "import sys, matplotlib, pandas, numpy; print(sys.version.split()[0], 'matplotlib', matplotlib.__version__, 'pandas', pandas.__version__, 'numpy', numpy.__version__)"

echo
echo "=== 容器内全流程复算（输入只读挂载 /in，输出挂载 /out）==="
docker run --rm --entrypoint python3 \
  -v "$PKG/solution/golden_output:/sol:ro" \
  -v "$PKG/environment/input_files:/in:ro" \
  -v "$OUT:/out" \
  fin3-wkn-149:local /sol/FIN3-WKN-149_reproduce.py /in /out
rc=$?
echo "reproduce rc=$rc"

echo
echo "=== 产物 ==="
find "$OUT" -type f -printf '%s\t%p\n' | sort -k2
