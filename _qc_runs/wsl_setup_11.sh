#!/bin/bash
# WSL 重建 第 11 步：持久化代理 + 安装 pip/docker/harbor
set -u
PROXY_PORT=18080

echo "======== 1) 写持久代理配置（动态网关，/etc/profile.d）========"
cat > /etc/profile.d/proxy.sh <<EOF
# WSL 出站必须走 Windows 侧 pproxy（Hyper-V 防火墙拦直连 TCP）
_gw=\$(ip route 2>/dev/null | awk '/^default/{print \$3; exit}')
if [ -n "\$_gw" ]; then
  export http_proxy="http://\$_gw:${PROXY_PORT}"
  export https_proxy="http://\$_gw:${PROXY_PORT}"
  export HTTP_PROXY="http://\$_gw:${PROXY_PORT}"
  export HTTPS_PROXY="http://\$_gw:${PROXY_PORT}"
  export no_proxy="localhost,127.0.0.1,::1,10.255.255.254"
  export NO_PROXY="\$no_proxy"
fi
unset _gw
EOF
chmod +x /etc/profile.d/proxy.sh
echo "  已写 /etc/profile.d/proxy.sh:"
cat /etc/profile.d/proxy.sh | sed 's/^/    /'

# 同时给 root/cron/systemd 环境
cat > /etc/environment.d/90-proxy.conf <<EOF
http_proxy=http://172.19.240.1:${PROXY_PORT}
https_proxy=http://172.19.240.1:${PROXY_PORT}
EOF

GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:$PROXY_PORT"
export https_proxy="http://GW_PLACEHOLDER"
export https_proxy="http://$GW:$PROXY_PORT"
export HTTP_PROXY="$http_proxy"; export HTTPS_PROXY="$https_proxy"
export no_proxy="localhost,127.0.0.1,::1"
echo "  当前会话代理: $https_proxy (GW=$GW)"

echo
echo "======== 2) 验证代理连通 ========"
code=$(timeout 25 curl -s -o /dev/null -w "%{http_code}" https://pypi.org/simple/ 2>/dev/null)
echo "  curl pypi (env): ${code:-失败}"

echo
echo "======== 3) 装 python3-pip 与软件源（走代理）========"
# 切 aliyun apt 源（更稳）
if [ -f /etc/apt/sources.list ]; then
  cp /etc/apt/sources.list /etc/apt/sources.list.bak-orig 2>/dev/null || true
  sed -i 's|http://archive.ubuntu.com/ubuntu|https://mirrors.aliyun.com/ubuntu|g; s|http://security.ubuntu.com/ubuntu|https://mirrors.aliyun.com/ubuntu|g' /etc/apt/sources.list
  echo "  apt 源已切 aliyun"
fi
timeout 180 apt-get update 2>&1 | tail -4
timeout 300 apt-get install -y python3-pip ca-certificates curl gnupg 2>&1 | tail -6
python3 -m pip --version 2>&1 | head -2

echo
echo "======== 4) pip 配 aliyun 源 + 装 harbor ========"
mkdir -p /root/.config/pip /home/wff/.config/pip
for d in /root/.config/pip /home/wff/.config/pip; do
  cat > "$d/pip.conf" <<'EOF'
[global]
index-url = https://mirrors.aliyun.com/pypi/simple/
trusted-host = mirrors.aliyun.com
timeout = 60
EOF
done
echo "  pip.conf 已配（aliyun）"
timeout 300 python3 -m pip install --upgrade pip 2>&1 | tail -3
echo "  --- 安装 harbor==0.22.0 ---"
timeout 600 python3 -m pip install "harbor==0.22.0" 2>&1 | tail -8
echo "  --- 验证 ---"
python3 -c "import harbor, sys; print('  harbor import OK', getattr(harbor,'__version__','?'))" 2>&1 | head -3
command -v harbor && harbor --version 2>&1 | head -3 || echo "  harbor 命令不在 PATH（试 python3 -m harbor.cli --help）"
python3 -m harbor.cli --help 2>&1 | head -6 || python3 -m harbor --help 2>&1 | head -6 || true

echo
echo "STEP11-DONE"
