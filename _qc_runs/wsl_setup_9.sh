#!/bin/bash
# WSL 重建 第 9 步：修复默认路由指向 DOWN 接口的问题
set -u

echo "======== 1) 接口状态 ========"
ip -br addr
echo "--- link 详情 ---"
ip -br link

echo
echo "======== 2) 当前默认路由（问题所在）========"
ip route | head -6

echo
echo "======== 3) 修复：up 所有 DOWN 的非 loopback 接口 ========"
for i in $(ip -br link | awk '$1!="lo" && $2=="DOWN"{print $1}'); do
  echo "  ip link set $i up"
  ip link set "$i" up 2>&1
done
sleep 2
ip -br link

echo
echo "======== 4) 若默认路由仍指向 DOWN 接口，改指 UP 的接口 ========"
defdev=$(ip route | awk '/^default/{print $5; exit}')
defgw=$(ip route | awk '/^default/{print $3; exit}')
state=$(ip -br link | awk -v d="$defdev" '$1==d{print $2}')
echo "  默认路由: via $defgw dev $defdev (state=$state)"
if [ "$state" != "UP" ] && [ -n "$state" ]; then
  updev=$(ip -br link | awk '$1!="lo" && $2=="UP"{print $1; exit}')
  if [ -n "$updev" ]; then
    echo "  修正: ip route replace default via $defgw dev $updev"
    ip route replace default via "$defgw" dev "$updev"
    sleep 1
  fi
fi
echo "  修正后默认路由: $(ip route | awk '/^default/{print}')"

echo
echo "======== 5) 网络测试（修复后）========"
code=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" https://pypi.org/simple/ 2>/dev/null)
echo "  pypi.org:           ${code:-失败}"
code=$(timeout 20 curl -4 -s -A "pip/26.1" -o /dev/null -w "%{http_code}" https://mirrors.aliyun.com/pypi/simple/pip/ 2>/dev/null)
echo "  aliyun pypi:        ${code:-失败}"
code=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" https://fanrenapi.com 2>/dev/null)
echo "  fanrenapi.com:      ${code:-失败}"
code=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" https://4router.net 2>/dev/null)
echo "  4router.net:        ${code:-失败}"
code=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" https://registry.npmjs.org/ 2>/dev/null)
echo "  npmjs:              ${code:-失败}"
code=$(timeout 25 curl -4 -s -o /dev/null -w "%{http_code}" "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/" 2>/dev/null)
echo "  阿里云 llm(判官):    ${code:-失败}"

echo
echo "======== 6) apt/pip 复测 ========"
timeout 60 apt-get update 2>&1 | tail -3
echo "  ensurepip: $(python3 -m ensurepip --version 2>&1 | head -1)"

echo
echo "STEP9-DONE"
