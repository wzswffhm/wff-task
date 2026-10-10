#!/bin/bash
# WSL 重建 第 16 步：装 python3.13（去掉不存在的 distutils）+ 装 harbor
set -u
PROXY_PORT=18080
GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:$PROXY_PORT" https_proxy="http://$GW:$PROXY_PORT"
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
export no_proxy="localhost,127.0.0.1,::1"
echo "  代理: $https_proxy"

echo
echo "======== 1) 可用的 3.13 包 ========"
apt-cache search --names-only '^python3\.13' 2>/dev/null | sed 's/^/  /' | head -12

echo
echo "======== 2) 装 python3.13 + venv ========"
timeout 420 apt-get install -y python3.13 python3.13-venv 2>&1 | tail -6
python3.13 --version 2>&1 || echo "  python3.13 仍不可用"

echo
echo "======== 3) 装 pip（get-pip）========"
if command -v python3.13 >/dev/null 2>&1; then
  if ! python3.13 -m pip --version >/dev/null 2>&1; then
    timeout 120 curl -sSL -o /tmp/get-pip.py https://bootstrap.pypa.io/get-pip.py && echo "  get-pip 下载 OK" || echo "  get-pip 下载失败"
    [ -s /tmp/get-pip.py ] && timeout 300 python3.13 /tmp/get-pip.py 2>&1 | tail -4
  fi
  python3.13 -m pip --version 2>&1 | head -2

  echo
  echo "======== 4) 装 harbor==0.22.0 ========"
  timeout 900 python3.13 -m pip install --index-url https://pypi.org/simple "harbor==0.22.0" 2>&1 | tail -8

  echo
  echo "======== 5) 验证 ========"
  python3.13 -c "import harbor; print('  harbor import OK', getattr(harbor,'__version__','?'))" 2>&1 | head -2
  for p in /usr/local/bin/harbor /usr/bin/harbor /root/.local/bin/harbor /home/wff/.local/bin/harbor; do
    [ -x "$p" ] && { echo "  found: $p"; timeout 60 "$p" --version 2>&1 | head -2; }
  done
  python3.13 - <<'PY'
try:
    from importlib.metadata import entry_points
    eps = entry_points()
    sel = eps.select(group='console_scripts') if hasattr(eps, 'select') else []
    hits = [e for e in sel if 'harbor' in e.name]
    for e in hits:
        print(f"  entry: {e.name} -> {e.value}")
    if not hits:
        print("  无 harbor console_script")
except Exception as ex:
    print("  ep 查询失败:", ex)
PY
else
  echo "  python3.13 未装上，退出"
fi

echo
echo "STEP16-DONE"
