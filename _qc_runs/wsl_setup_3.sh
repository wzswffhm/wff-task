#!/bin/bash
# WSL 重建 第 3 步：网络路由诊断
set -u

echo "======== 1) 网卡与路由 ========"
ip -br addr 2>/dev/null || ifconfig -a 2>/dev/null | head -20
echo "--- route ---"
ip route 2>/dev/null
echo "--- 默认网关连通性 ---"
gw=$(ip route | awk '/default/{print $3; exit}')
echo "  网关=$gw"
if [ -n "$gw" ]; then
  timeout 5 ping -c 3 -W 2 "$gw" 2>&1 | tail -3 || echo "  ping 网关失败"
fi

echo
echo "======== 2) Windows 主机连通性 ========"
wintaskip=$(ip route | awk '/^default/{print $3; exit}')
echo "  尝试网关:443（Windows 主机）"
timeout 5 bash -c "echo > /dev/tcp/$wintaskip/443" 2>&1 && echo "  可连 443" || echo "  不可连 443"

echo
echo "======== 3) 常见公共 IP 直连测试（绕过 DNS）========"
for ip in 1.1.1.1 8.8.8.8 223.5.5.5; do
  timeout 5 ping -c 2 -W 2 "$ip" >/dev/null 2>&1 && echo "  ping $ip 通" || echo "  ping $ip 不通"
done

echo
echo "======== 4) IPv4/IPv6 出站 ========"
echo "  强制 IPv4 curl aliyun:"
timeout 12 curl -4 -s -o /dev/null -w "  http=%{http_code} time=%{time_total}s\n" https://mirrors.aliyun.com/ || echo "  IPv4 失败 rc=$?"
echo "  强制 IPv4 curl pypi:"
timeout 12 curl -4 -s -o /dev/null -w "  http=%{http_code} time=%{time_total}s\n" https://pypi.org/simple/ || echo "  IPv4 失败 rc=$?"

echo
echo "======== 5) Windows 侧代理线索（wsl.conf / .wslconfig）========"
echo "--- /etc/wsl.conf ---"
cat /etc/wsl.conf 2>/dev/null
echo "--- Windows .wslconfig ---"
cat /mnt/c/Users/Administrator/.wslconfig 2>/dev/null || echo "  (无 .wslconfig)"

echo
echo "======== 6) 测试 Windows 主机上的代理端口（常见本地代理）========"
for p in 7890 7897 1080 8118 8888 33210; do
  timeout 3 bash -c "echo > /dev/tcp/$wintaskip/$p" 2>/dev/null && echo "  $wintaskip:$p 开放" || true
done
echo "  (未列出即无常见代理端口)"

echo
echo "STEP3-DONE"
