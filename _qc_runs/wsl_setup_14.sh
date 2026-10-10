#!/bin/bash
# WSL 重建 第 14 步：给 pip 显式配代理（pip.conf proxy）+ verbose 诊断 + 3.10 兼容离线兜底
set -u
PROXY_PORT=18080
GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:$PROXY_PORT" https_proxy="http://$GW:$PROXY_PORT"
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
export no_proxy="localhost,127.0.0.1,::1"
P="http://$GW:$PROXY_PORT"
echo "  代理: $P"

echo
echo "======== 1) pip.conf 写入显式 proxy ========"
for d in /root/.config/pip /home/wff/.config/pip /etc/pip.conf; do
  if [ -d "$d" ]; then
    cat > "$d/pip.conf" <<EOF
[global]
proxy = $P
index-url = https://pypi.org/simple
trusted-host = pypi.org files.pythonhosted.org
timeout = 60
retries = 3
EOF
    echo "  已写 $d/pip.conf"
  elif [ "$d" = "/etc/pip.conf" ]; then
    cat > "$d" <<EOF
[global]
proxy = $P
index-url = https://pypi.org/simple
trusted-host = pypi.org files.pythonhosted.org
timeout = 60
retries = 3
EOF
    echo "  已写 $d"
  fi
done

echo
echo "======== 2) pip 版本与代理环境 ========"
python3 -m pip --version
echo "  https_proxy=$https_proxy"

echo
echo "======== 3) verbose 试装 harbor（看 pip 实际请求）========"
timeout 300 python3 -m pip install -v "harbor==0.22.0" 2>&1 | grep -iE "Looking in|Getting|Created connection|Proxy|error|ERROR|Collecting|Downloading|Installing|Successfully" | head -25

echo
echo "======== 4) 验证 ========"
python3 -c "import harbor; print('  harbor OK', getattr(harbor,'__version__','?'))" 2>&1 | head -2
ls -la /usr/local/bin/harbor 2>/dev/null && timeout 60 /usr/local/bin/harbor --version 2>&1 | head -3

echo
echo "STEP14-DONE"
