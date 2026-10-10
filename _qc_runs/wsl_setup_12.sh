#!/bin/bash
# WSL 重建 第 12 步：启用 universe 仓库并装 pip，再装 harbor
set -u
PROXY_PORT=18080
GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:$PROXY_PORT" https_proxy="http://$GW:$PROXY_PORT"
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
export no_proxy="localhost,127.0.0.1,::1"
echo "  代理: $https_proxy"

echo
echo "======== 1) 当前 sources.list ========"
grep -hE "^deb " /etc/apt/sources.list /etc/apt/sources.list.d/*.list 2>/dev/null | sed 's/^/  /' | head -20

echo
echo "======== 2) 启用 universe / multiverse（python3-pip 在 universe）========"
SL=/etc/apt/sources.list
[ -f "$SL.orig-$(date +%s)" ] || cp "$SL" "$SL.bak-universe" 2>/dev/null || true
# 旧格式：在每个 jammy 行补全组件
python3 - <<'PY'
import re, pathlib
p = pathlib.Path("/etc/apt/sources.list")
t = p.read_text(encoding="utf-8", errors="replace")
need = False
out = []
for line in t.splitlines():
    m = re.match(r"^(deb\s+\S+\s+\S+)\s+(.*)$", line)
    if m and not line.startswith("#"):
        comps = m.group(2).split()
        for c in ("universe", "multiverse"):
            if c not in comps:
                comps.append(c); need = True
        line = m.group(1) + " " + " ".join(comps)
    out.append(line)
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"  已补全 universe/multiverse: {need}")
PY
grep -hE "^deb " "$SL" | sed 's/^/  /' | head -8

echo
echo "======== 3) apt update + 装 python3-pip ========"
timeout 240 apt-get update 2>&1 | tail -3
timeout 420 apt-get install -y python3-pip 2>&1 | tail -8
python3 -m pip --version 2>&1 | head -2

echo
echo "======== 4) 若 pip 仍缺，用 get-pip.py 兜底 ========"
if ! python3 -m pip --version >/dev/null 2>&1; then
  echo "  下载 get-pip.py（走代理）"
  timeout 90 curl -sSL -o /tmp/get-pip.py https://bootstrap.pypa.io/get-pip.py && echo "  下载成功" || echo "  下载失败"
  if [ -s /tmp/get-pip.py ]; then
    timeout 300 python3 /tmp/get-pip.py --break-system-packages 2>&1 | tail -5
    python3 -m pip --version 2>&1 | head -2
  fi
fi

echo
echo "======== 5) 装 harbor==0.22.0 ========"
if python3 -m pip --version >/dev/null 2>&1; then
  # 优先用本地离线 wheel（Windows 侧已下载），失败则走 aliyun 在线
  WHEELS=/mnt/c/Users/Administrator/Desktop/wff-task/_qc_runs/wsl_wheels
  if [ -d "$WHEELS" ]; then
    echo "  尝试离线安装（$WHEELS）"
    timeout 600 python3 -m pip install --no-index --find-links "$WHEELS" "harbor==0.22.0" 2>&1 | tail -6
  fi
  if ! python3 -c "import harbor" >/dev/null 2>&1; then
    echo "  离线失败，在线装（aliyun 源）"
    timeout 600 python3 -m pip install "harbor==0.22.0" 2>&1 | tail -8
  fi
  echo "  --- 验证 ---"
  python3 -c "import harbor; print('  harbor import OK', getattr(harbor,'__version__','?'))" 2>&1 | head -2
  ls -la /usr/local/bin/harbor 2>/dev/null && harbor --version 2>&1 | head -3 || true
  python3 -c "
from importlib.metadata import entry_points
eps = entry_points()
sel = eps.select(group='console_scripts') if hasattr(eps,'select') else eps.get('console_scripts',[])
for e in sel:
    if 'harbor' in (e.name or ''):
        print('  console_script:', e.name, '->', e.value)
" 2>&1 | head -6
else
  echo "  pip 仍不可用，跳过 harbor"
fi

echo
echo "STEP12-DONE"
