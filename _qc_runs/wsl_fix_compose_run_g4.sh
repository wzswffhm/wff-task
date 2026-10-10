#!/bin/bash
# 装 docker compose v2 插件（GitHub 二进制，走代理）+ 重跑 G4
set -u
PROXY_PORT=18080
GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:$PROXY_PORT" https_proxy="http://$GW:$PROXY_PORT" no_proxy="localhost,127.0.0.1"
echo "代理: $https_proxy"

echo
echo "======== 1) 装 docker compose 插件 ========"
mkdir -p /usr/local/lib/docker/cli-plugins
if docker compose version >/dev/null 2>&1; then
  echo "  [已有] $(docker compose version 2>&1 | head -1)"
else
  echo "  下载 docker-compose-linux-x86_64 ..."
  timeout 300 curl -fsSL -o /tmp/docker-compose \
    https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-x86_64 \
    && echo "  下载 OK ($(stat -c%s /tmp/docker-compose 2>/dev/null) B)" || echo "  下载失败"
  if [ -s /tmp/docker-compose ]; then
    install -m 0755 /tmp/docker-compose /usr/local/lib/docker/cli-plugins/docker-compose
    ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose
    rm -f /tmp/docker-compose
  fi
  # 也放到用户级目录兜底
  mkdir -p /root/.docker/cli-plugins
  [ -f /usr/local/lib/docker/cli-plugins/docker-compose ] && \
    ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /root/.docker/cli-plugins/docker-compose
  echo "  --- 验证 ---"
  docker compose version 2>&1 | head -3 || echo "  docker compose 仍不可用"
fi

echo
echo "======== 2) 重跑 G4 oracle ========"
if docker compose version >/dev/null 2>&1; then
  bash /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g4_v4_run.sh
  rc=$?
  echo "G4-RERUN-EXIT=$rc"
else
  echo "G4-RERUN-EXIT=99 compose 未装上，跳过"
  exit 99
fi
