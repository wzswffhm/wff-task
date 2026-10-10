#!/bin/bash
# WSL 重建 第 4 步：定位 TCP 不通的根因（80 vs 443 / MTU / 代理）
set -u

echo "======== 1) TCP 分辨：80 vs 443 vs 53 ========"
for tgt in "151.101.64.223 443" "151.101.64.223 80" "223.5.5.5 53" "223.5.5.5 443" "1.1.1.1 443"; do
  set -- $tgt
  timeout 6 bash -c "echo > /dev/tcp/$1/$2" 2>/dev/null && echo "  $1:$2  可连" || echo "  $1:$2  不可连"
done

echo
echo "======== 2) HTTP(80) vs HTTPS(443) ========"
timeout 10 curl -4 -s -o /dev/null -w "  http(80) aliyun: http=%{http_code} t=%{time_total}\n" http://mirrors.aliyun.com/ || echo "  http(80) 失败 rc=$?"
timeout 10 curl -4 -s -o /dev/null -w "  https(443) aliyun: http=%{http_code} t=%{time_total}\n" https://mirrors.aliyun.com/ || echo "  https(443) 失败 rc=$?"

echo
echo "======== 3) MTU 分片测试 ========"
echo "  当前 MTU: $(ip link show eth0 2>/dev/null | grep -o 'mtu [0-9]*')"
for s in 1472 1400 1300 1200; do
  if timeout 4 ping -M do -s $s -c 2 -W 2 1.1.1.1 >/dev/null 2>&1; then echo "  MTU 分片 do -s $s  通"; else echo "  MTU 分片 do -s $s  不通"; fi
done

echo
echo "======== 4) 尝试降低 MTU 后再测 TCP ========"
ip link set dev eth0 mtu 1400 2>/dev/null && echo "  已设 MTU=1400" || echo "  设 MTU 失败"
sleep 1
timeout 8 curl -4 -s -o /dev/null -w "  https(443) aliyun: http=%{http_code} t=%{time_total}\n" https://mirrors.aliyun.com/ || echo "  仍失败 rc=$?"

echo
echo "======== 5) Windows 主机可达端口扫描（网关=主机）========"
gw=$(ip route | awk '/default/{print $3; exit}')
echo "  网关/主机 = $gw"
for p in 22 80 443 7897 8899 33210 53 2375 2376; do
  timeout 2 bash -c "echo > /dev/tcp/$gw/$p" 2>/dev/null && echo "    $p 开放" || true
done
echo "  (未列出即不通)"

echo
echo "======== 6) 是否可走 Windows 代理（127.0.0.1 与 主机IP 两种）========"
for proxy in "127.0.0.1:7897" "$gw:7897" "127.0.0.1:8899" "$gw:8899"; do
  code=$(timeout 8 curl -4 -s -o /dev/null -w "%{http_code}" -x "http://$proxy" https://pypi.org/simple/ 2>/dev/null)
  [ -n "$code" ] && [ "$code" != "000" ] && echo "  代理 $proxy -> http=$code  可用" || echo "  代理 $proxy -> 不可用"
done

echo
echo "STEP4-DONE"
