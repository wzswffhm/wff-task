#!/bin/bash
# 重新构建 fin3-wkn-152:local（v3：legacy builder，因 buildx 缺失）
set -u
PROXY_PORT=18080
GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:$PROXY_PORT" https_proxy="http://$GW:$PROXY_PORT" no_proxy="localhost,127.0.0.1"
echo "构建 fin3-wkn-152:local (legacy builder) 代理=$https_proxy"

# 确保 daemon Environment 指向当前网关（legacy builder 从 daemon 继承）
mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/proxy.conf <<EOF
[Service]
Environment="HTTP_PROXY=$http_proxy"
Environment="HTTPS_PROXY=$https_proxy"
Environment="NO_PROXY=localhost,127.0.0.1"
EOF
systemctl daemon-reload
systemctl restart docker
sleep 6
echo "  docker: $(systemctl is-active docker)"
echo "  daemon env: $(systemctl show docker -p Environment | grep -o 'HTTPS_PROXY=[^ ]*')"

cd /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/FIN3-WKN-152/environment || exit 9
date '+%F %T 开始'
export DOCKER_BUILDKIT=0
docker build -t fin3-wkn-152:local . 2>&1 | tail -35
rc=${PIPESTATUS[0]}
date '+%F %T 结束 rc='"$rc"
echo "--- 镜像列表 ---"
docker images --format "{{.Repository}}:{{.Tag}} {{.Size}}" | head -6
echo "BUILD-V3-DONE rc=$rc"
