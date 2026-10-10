#!/bin/bash
set -u
PROXY_PORT=18080
GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:$PROXY_PORT" https_proxy="http://$GW:$PROXY_PORT"
export no_proxy="localhost,127.0.0.1,::1"
echo "构建镜像 fin3-wkn-152:local  (代理 $https_proxy)"
cd /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/FIN3-WKN-152/environment || exit 9
echo "Dockerfile:"
ls -la Dockerfile requirements.txt 2>/dev/null
date '+%F %T 开始'
docker build -t fin3-wkn-152:local . 2>&1 | tail -30
rc=$?
date '+%F %T 结束 rc='$rc
docker images | head -5
echo "BUILD-DONE rc=$rc"