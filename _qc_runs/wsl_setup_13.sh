#!/bin/bash
# WSL 重建 第 13 步：从官方 pypi 装 harbor（走代理，aliyun 镜像缺该包）
set -u
PROXY_PORT=18080
GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:$PROXY_PORT" https_proxy="http://$GW:$PROXY_PORT"
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
export no_proxy="localhost,127.0.0.1,::1"
echo "  代理: $https_proxy"

echo
echo "======== 0) 代理连通确认 ========"
echo "  pypi: $(timeout 25 curl -s -o /dev/null -w '%{http_code}' https://pypi.org/simple/harbor/)"

echo
echo "======== 1) 官方 pypi 装 harbor==0.22.0 ========"
timeout 900 python3 -m pip install --index-url https://pypi.org/simple --upgrade "harbor==0.22.0" 2>&1 | tail -14

echo
echo "======== 2) 验证 ========"
python3 -c "import harbor; print('  harbor import OK', getattr(harbor,'__version__','?'))" 2>&1 | head -3
if [ -x /usr/local/bin/harbor ]; then
  echo "  /usr/local/bin/harbor 存在"
  timeout 60 harbor --version 2>&1 | head -3
else
  echo "  /usr/local/bin/harbor 缺失，查 entry point:"
  python3 - <<'PY'
try:
    from importlib.metadata import entry_points
    eps = entry_points()
    sel = eps.select(group='console_scripts') if hasattr(eps, 'select') else []
    found = [e for e in sel if 'harbor' in e.name]
    for e in found:
        print(f"  entry: {e.name} -> {e.value}")
    if not found:
        print("  无 harbor console_script")
except Exception as ex:
    print("  查询失败:", ex)
PY
  ls -la /usr/local/bin/ 2>/dev/null | grep -i harbor || echo "  /usr/local/bin 无 harbor"
fi

echo
echo "======== 3) harbor CLI 关键子命令探测 ========"
HB=$(command -v harbor || echo "")
if [ -n "$HB" ]; then
  echo "  harbor = $HB"
  timeout 60 "$HB" --help 2>&1 | head -20
  echo "  --- trial 子命令 ---"
  timeout 60 "$HB" trial --help 2>&1 | head -20
else
  echo "  harbor 不在 PATH；用 python -m 试"
  timeout 60 python3 -m harbor.cli --help 2>&1 | head -15 || true
fi

echo
echo "STEP13-DONE"
