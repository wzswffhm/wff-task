#!/bin/bash
# 重新构建 fin3-wkn-152:local（基础镜像 apt 源已改造为 aliyun）
set -u
PROXY_PORT=18080
GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:$PROXY_PORT" https_proxy="http://$GW:$PROXY_PORT" no_proxy="localhost,127.0.0.1"
echo "构建 fin3-wkn-152:local  代理=$https_proxy"

# BuildKit 需要的代理配置（写 docker config，比 daemon Environment 更可靠）
mkdir -p /root/.docker
cat > /root/.docker/config.json <<EOF
{
  "proxies": {
    "default": {
      "httpProxy": "$http_proxy",
      "httpsProxy": "$https_proxy",
      "noProxy": "localhost,127.0.0.1"
    }
  }
}
EOF
echo "  已写 /root/.docker/config.json proxies"

cd /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/FIN3-WKN-152/environment || exit 9
date '+%F %T 开始'
export DOCKER_BUILDKIT=1
docker build -t fin3-wkn-152:local . 2>&1 | tail -40
rc=${PIPESTATUS[0]}
date '+%F %T 结束 rc='"$rc"
echo "--- 镜像列表 ---"
docker images --format "{{.Repository}}:{{.Tag}} {{.Size}}" | head -6
echo "BUILD-V2-DONE rc=$rc"
