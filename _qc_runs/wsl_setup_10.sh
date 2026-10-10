#!/bin/bash
# WSL 重建 第 10 步：清除 mirrored 自带的 nftables mark/masquerade 规则并测试
set -u

echo "======== 1) 清空前的规则 ========"
nft list ruleset 2>/dev/null | head -25

echo
echo "======== 2) 清空 nftables 规则 ========"
nft flush ruleset 2>&1 && echo "  已 flush" || echo "  flush 失败"
sleep 1
echo "  清空后规则:"
nft list ruleset 2>/dev/null | head -8 || echo "  (空)"

echo
echo "======== 3) 清空后网络测试 ========"
code=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" https://pypi.org/simple/ 2>/dev/null)
echo "  pypi.org:           ${code:-失败}"
code=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" https://fanrenapi.com 2>/dev/null)
echo "  fanrenapi.com:      ${code:-失败}"
code=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" https://4router.net 2>/dev/null)
echo "  4router.net:        ${code:-失败}"

echo
echo "======== 4) 若仍失败，检查出站包统计（能否发出）========"
echo "  接口统计:"
ip -s link show eth1 2>/dev/null | head -8
echo "  路由:"
ip route | head -4
echo "  ARP:"
ip neigh | head -6

echo
echo "======== 5) traceroute 探测第一跳 ========"
timeout 20 traceroute -n -m 5 -w 2 1.1.1.1 2>/dev/null | head -8 || {
  echo "  traceroute 不可用，改用 ping 计时:"
  timeout 10 ping -c 4 -W 2 1.1.1.1 2>&1 | tail -3
}

echo
echo "======== 6) 与 Windows 主机（网关）TCP 交互 ========"
gw=$(ip route | awk '/default/{print $3; exit}')
for p in 443 80 53; do
  if timeout 5 bash -c "exec 3<>/dev/tcp/$gw/$p" 2>/dev/null; then echo "  网关:$p 可连"; else echo "  网关:$p 不可连"; fi
done
echo "  ping 网关: $(timeout 5 ping -c 2 -W 2 $gw 2>&1 | grep -o '[0-9]*% packet loss' || echo '无响应')"

echo
echo "STEP10-DONE"
