#!/bin/bash
# WSL 重建 第 5 步：mirrored 模式下网络验证
set -u

echo "======== 1) 网卡（mirrored 应与 Windows 一致）========"
ip -br addr 2>/dev/null | head -8
echo "--- route ---"
ip route | head -5

echo
echo "======== 2) TCP 连通 ========"
for tgt in "pypi.org 443" "mirrors.aliyun.com 443" "archive.ubuntu.com 80"; do
  set -- $tgt
  if timeout 8 bash -c "exec 3<>/dev/tcp/$1/$2" 2>/dev/null; then
    echo "  $1:$2  可连"
  else
    echo "  $1:$2  不可连"
  fi
done

echo
echo "======== 3) curl 实测 ========"
code1=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" https://pypi.org/simple/ 2>/dev/null)
echo "  pypi https: http=${code1:-失败}"
code2=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" https://mirrors.aliyun.com/ 2>/dev/null)
echo "  aliyun https: http=${code2:-失败}"
code3=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" http://archive.ubuntu.com/ubuntu/ 2>/dev/null)
echo "  ubuntu http: http=${code3:-失败}"

echo
echo "======== 4) apt 测试 ========"
timeout 90 apt-get update 2>&1 | tail -3

echo
echo "======== 5) pip 测试 ========"
timeout 45 python3 -m ensurepip --version 2>&1 | head -2 || echo "  ensurepip 不可用"
code4=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" https://pypi.org/simple/pip/ 2>/dev/null)
echo "  pypi/pip: http=${code4:-失败}"

echo
echo "STEP5-DONE"
