#!/bin/bash
# WSL 重建 第 17 步：WSL 内独立 docker engine（不依赖 Docker Desktop）+ harbor trial 验证
set -u
PROXY_PORT=18080
GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:$PROXY_PORT" https_proxy="http://$GW:$PROXY_PORT"
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
export no_proxy="localhost,127.0.0.1,::1"
echo "  代理: $https_proxy"

echo
echo "======== 1) 装 docker.io ========"
timeout 600 apt-get install -y docker.io 2>&1 | tail -6
command -v docker && docker --version 2>&1 | head -2 || echo "  docker 未装上"

echo
echo "======== 2) 启动 docker.service（systemd）========"
systemctl daemon-reload 2>&1 | tail -2
systemctl enable docker 2>&1 | tail -2
systemctl start docker 2>&1 | tail -3
sleep 5
systemctl is-active docker 2>&1
echo "  --- docker info 摘要 ---"
timeout 30 docker info 2>&1 | grep -E "Server Version|Storage Driver|Docker Root Dir|ERROR|Cannot connect" | head -6

echo
echo "======== 3) docker 代理（构建镜像/拉基础镜像需要）========="
mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/proxy.conf <<EOF
[Service]
Environment="HTTP_PROXY=http://$GW:$PROXY_PORT"
Environment="HTTPS_PROXY=http://$GW:$PROXY_PORT"
Environment="NO_PROXY=localhost,127.0.0.1"
EOF
systemctl daemon-reload
systemctl restart docker 2>&1 | tail -2
sleep 5
systemctl is-active docker
echo "  (网关会变，此配置需在每次 WSL 重启后刷新 - 见第 18 步自愈脚本)"

echo
echo "======== 4) docker 拉取测试（python:3.12-slim 基础镜像）========"
timeout 300 docker pull python:3.12-slim 2>&1 | tail -5

echo
echo "======== 5) harbor trial 子命令验证（只看帮助，不跑）========="
timeout 60 harbor --help 2>&1 | head -25
echo "  --- trial ---"
timeout 60 harbor trial --help 2>&1 | head -25

echo
echo "STEP17-DONE"
