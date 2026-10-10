#!/bin/bash
# 测试 WSL 经 Windows 代理的出站能力
set -u
PROXY="$1"
echo "======== 经代理 $PROXY 出站测试 ========"
for u in "https://pypi.org/simple/" "https://mirrors.aliyun.com/ubuntu/dists/jammy/Release" \
         "https://fanrenapi.com" "https://4router.net" \
         "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com" \
         "https://registry.npmjs.org/"; do
  code=$(timeout 30 curl -4 -s -o /dev/null -w "%{http_code}" -x "http://$PROXY" "$u" 2>/dev/null)
  printf '  %-4s %s\n' "${code:-超时}" "$u"
done

echo
echo "======== 直连对照（应全失败）========"
code=$(timeout 15 curl -4 -s -o /dev/null -w "%{http_code}" https://pypi.org/simple/ 2>/dev/null)
echo "  直连 pypi: ${code:-失败}"

echo
echo "======== 代理端口 TCP 可达性 ========"
host="${PROXY%%:*}"; port="${PROXY##*:}"
if timeout 5 bash -c "exec 3<>/dev/tcp/$host/$port" 2>/dev/null; then
  echo "  $host:$port 可连 ✓"
else
  echo "  $host:$port 不可连 ✗"
fi
echo "STEP-PROXY-DONE"
