#!/bin/bash
# WSL 重建 第 19 步：给 v4 跑分脚本注入代理（systemd 调用时不 source profile）
set -u
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
PROXY_SNIPPET='
# --- WSL 出站必须走 Windows 侧 pproxy（本环境无直连 TCP）---
GW=$(ip route 2>/dev/null | awk "/^default/{print \$3; exit}")
if [ -n "${GW:-}" ]; then
  export http_proxy="http://$GW:18080" https_proxy="http://$GW:18080"
  export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
  export no_proxy="localhost,127.0.0.1,::1"
fi
unset GW
# --- end proxy ---
'

for f in g4_v4_run.sh g5_v4_run.sh g5_v4_opus_run.sh start_g4_v4.sh start_g5_v4.sh start_g5_v4_opus.sh; do
  p="$Q/$f"
  [ -f "$p" ] || { echo "  (缺 $f)"; continue; }
  if grep -q "WSL 出站必须走" "$p"; then
    echo "  [--] $f 已含代理注入"
    continue
  fi
  cp "$p" "$p.bak-noproxy"
  # 在 set -u / set -a 之后、第一个命令之前插入；简单起见插在首行 shebang 后
  python3.13 - "$p" <<PYEOF
import sys, io
p = sys.argv[1]
lines = io.open(p, encoding="utf-8").read().splitlines(True)
snippet = """$PROXY_SNIPPET"""
# 插在第 1 行 (shebang) 与第 2 行之间
out = [lines[0], snippet] + lines[1:]
io.open(p, "w", encoding="utf-8", newline="").writelines(out)
print(f"  [OK] 已注入代理 {p.split('/')[-1]}")
PYEOF
done

echo
echo "======== 校验 ========"
for f in g4_v4_run.sh g5_v4_run.sh g5_v4_opus_run.sh; do
  p="$Q/$f"
  [ -f "$p" ] || continue
  n=$(grep -c "WSL 出站必须走" "$p" 2>/dev/null || echo 0)
  h=$(grep -c "HOME=/home/wff" "$p" 2>/dev/null || echo 0)
  t=$(grep -c "harbor trial start" "$p" 2>/dev/null || echo 0)
  echo "  $f: proxy=$n HOME=$h trial_start=$t"
done

echo
echo "======== harbor 可执行与 PATH（模拟 systemd 环境）========"
env -i PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin HOME=/home/wff \
  bash -c 'harbor --version 2>&1 | head -1' || echo "  harbor 在干净 PATH 下不可用"
env -i PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin HOME=/home/wff \
  bash -c 'harbor trial start --help >/dev/null 2>&1 && echo "  trial start OK" || echo "  trial start FAIL"'

echo
echo "STEP19-DONE"
