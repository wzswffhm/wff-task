#!/bin/bash
# WSL 重建 第 18 步：修复 docker pull（代理/加速器）+ 网关自愈
set -u
PROXY_PORT=18080
GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:$PROXY_PORT" https_proxy="http://$GW:$PROXY_PORT"
export no_proxy="localhost,127.0.0.1,::1"
echo "  代理: $https_proxy"

echo
echo "======== 1) daemon 代理配置确认 ========"
systemctl show docker -p Environment 2>/dev/null | tr ' ' '\n' | grep -i proxy | sed 's/^/  /'
cat /etc/systemd/system/docker.service.d/proxy.conf 2>/dev/null | sed 's/^/  /'

echo
echo "======== 2) 经代理访问 docker registry ========"
code=$(timeout 25 curl -s -o /dev/null -w "%{http_code}" https://registry-1.docker.io/v2/ 2>/dev/null)
echo "  registry-1.docker.io/v2/: ${code:-失败}"
code=$(timeout 40 curl -s -o /dev/null -w "%{http_code} bytes=%{size_download}" -r 0-2000000 "https://registry-1.docker.io/v2/library/python/blobs/sha256:f83c8037875cdc6506ef83ab2a96a146e212c18156e1e5ccfded74bd13313953" 2>/dev/null)
echo "  blob 前 2MB 下载: ${code:-失败}"

echo
echo "======== 3) docker daemon 重启后重试 pull ========"
systemctl restart docker
sleep 6
timeout 300 docker pull python:3.12-slim 2>&1 | tail -4

echo
echo "======== 4) 若仍失败，配国内加速器（docker.io 镜像）========"
if ! docker images 2>/dev/null | grep -q "python.*3.12-slim"; then
  echo "  未拉到，写 daemon.json 加速器"
  cp /etc/docker/daemon.json /etc/docker/daemon.json.bak 2>/dev/null || true
  cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://dockerproxy.com",
    "https://mirror.ccs.tencentyun.com",
    "https://registry.cn-hangzhou.aliyuncs.com"
  ]
}
EOF
  systemctl restart docker
  sleep 6
  timeout 300 docker pull python:3.12-slim 2>&1 | tail -6
fi

echo
echo "======== 5) 结果确认 ========"
docker images 2>/dev/null | head -5
echo "  --- 已有镜像 ---"
docker images --format "  {{.Repository}}:{{.Tag}} {{.Size}}" 2>/dev/null | head -8

echo
echo "======== 6) 网关自愈脚本（WSL 每次启动自动刷新代理）========="
cat > /usr/local/bin/wsl-proxy-refresh.sh <<'REFRESH'
#!/bin/bash
# 每次 WSL 启动：按当前网关刷新代理配置（网关 IP 会变）
GW=$(ip route 2>/dev/null | awk '/^default/{print $3; exit}')
[ -z "$GW" ] && exit 0
PROXY="http://$GW:18080"
# docker daemon 代理
mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/proxy.conf <<EOF
[Service]
Environment="HTTP_PROXY=$PROXY"
Environment="HTTPS_PROXY=$PROXY"
Environment="NO_PROXY=localhost,127.0.0.1"
EOF
systemctl daemon-reload 2>/dev/null
systemctl restart docker 2>/dev/null
echo "$PROXY" > /var/run/wsl-proxy-active
REFRESH
chmod +x /usr/local/bin/wsl-proxy-refresh.sh
cat > /etc/systemd/system/wsl-proxy-refresh.service <<'SVC'
[Unit]
Description=Refresh WSL proxy for docker after boot
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/wsl-proxy-refresh.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
SVC
systemctl daemon-reload
systemctl enable wsl-proxy-refresh.service 2>&1 | tail -2
echo "  自愈服务已启用"

echo
echo "STEP18-DONE"
