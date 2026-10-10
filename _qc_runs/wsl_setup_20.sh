#!/bin/bash
# WSL 重建 第 20 步：让 build 的 apt 走得通（不改 Dockerfile —— 它是平台模板）
#   a) 先验证容器内经代理是否可访问 deb.debian.org
#   b) 若不可，本地改造 python:3.12-slim 的 apt 源为 aliyun（sed 文件，无需网络）后 commit 回同 tag
set -u
PROXY_PORT=18080
GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:$PROXY_PORT" https_proxy="http://$GW:$PROXY_PORT" no_proxy="localhost,127.0.0.1"
echo "  代理: $https_proxy"

echo
echo "======== 1) 容器内经代理访问 deb.debian.org ========"
timeout 60 docker run --rm \
  -e HTTP_PROXY="$http_proxy" -e HTTPS_PROXY="$https_proxy" \
  -e http_proxy="$http_proxy" -e https_proxy="$https_proxy" \
  python:3.12-slim bash -c '
    echo "  -- apt 源现状 --"; ls /etc/apt/sources.list* /etc/apt/sources.list.d/ 2>/dev/null
    echo "  -- 经代理 curl debian --"
    code=$(timeout 30 curl -s -o /dev/null -w "%{http_code}" http://deb.debian.org/debian/dists/trixie/InRelease 2>/dev/null)
    echo "  HTTP=${code:-失败}"
    code2=$(timeout 30 curl -s -o /dev/null -w "%{http_code}" https://mirrors.aliyun.com/debian/dists/trixie/InRelease 2>/dev/null)
    echo "  aliyun HTTPS=${code2:-失败}"
  ' 2>&1 | tail -12

echo
echo "======== 2) 改造本地基础镜像的 apt 源（无需网络）并 commit =========="
# 在容器里把 debian 源换成 aliyun，commit 回 python:3.12-slim
timeout 120 docker run --rm --name _fixsrc python:3.12-slim bash -c '
  set -e
  echo "  -- 识别源文件 --"
  if [ -f /etc/apt/sources.list.d/debian.sources ]; then
    echo "  deb822: /etc/apt/sources.list.d/debian.sources"
    cp /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list.d/debian.sources.orig
    sed -i "s|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g; s|http://deb.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g" /etc/apt/sources.list.d/debian.sources
    cat /etc/apt/sources.list.d/debian.sources
  elif [ -f /etc/apt/sources.list ]; then
    echo "  传统: /etc/apt/sources.list"
    cp /etc/apt/sources.list /etc/apt/sources.list.orig
    sed -i "s|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g; s|http://security.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g" /etc/apt/sources.list
    cat /etc/apt/sources.list
  else
    echo "  未找到源文件"
    ls -la /etc/apt/
  fi
' 2>&1 | tail -16

echo
echo "  (上一步 run --rm 已丢弃改动，改用分步: 用一个持久容器改后 commit)"

CID=$(timeout 60 docker create python:3.12-slim bash -c "sleep 5" 2>/dev/null)
echo "  临时容器: $CID"
if [ -n "$CID" ]; then
  timeout 60 docker start "$CID" >/dev/null 2>&1
  timeout 120 docker exec "$CID" bash -c '
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then
      sed -i "s|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g; s|http://deb.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g" /etc/apt/sources.list.d/debian.sources
      echo "  [改] debian.sources:"; grep -E "^URIs" /etc/apt/sources.list.d/debian.sources
    fi
    if [ -f /etc/apt/sources.list ]; then
      sed -i "s|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g; s|http://security.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g" /etc/apt/sources.list
      echo "  [改] sources.list:"; grep -E "^deb " /etc/apt/sources.list | head -4
    fi
  ' 2>&1 | tail -10
  docker commit "$CID" python:3.12-slim >/dev/null 2>&1 && echo "  [OK] 已 commit 回 python:3.12-slim" || echo "  commit 失败"
  docker rm -f "$CID" >/dev/null 2>&1
fi

echo
echo "======== 3) 验证改造后容器内 apt update ========"
timeout 120 docker run --rm \
  -e HTTP_PROXY="$http_proxy" -e HTTPS_PROXY="$https_proxy" \
  -e http_proxy="$http_proxy" -e https_proxy="$https_proxy" \
  python:3.12-slim bash -c 'timeout 90 apt-get update 2>&1 | tail -5' 2>&1 | tail -8

echo
echo "STEP20-DONE"
