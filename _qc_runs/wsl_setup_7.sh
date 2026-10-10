#!/bin/bash
# WSL 重建 第 7 步：看 curl 失败的确切阶段 + iptables 规则
set -u

echo "======== 1) curl -v pypi（看失败在哪个阶段）========"
timeout 25 curl -4 -v -o /dev/null https://pypi.org/simple/ 2>&1 | grep -E "Trying|Connected|SSL|TLS|HTTP|error|refused|reset|timed|Closing" | head -16

echo
echo "======== 2) curl -v aliyun（TCP 可连的那个）========"
timeout 25 curl -4 -v -o /dev/null https://mirrors.aliyun.com/ 2>&1 | grep -E "Trying|Connected|SSL|TLS|HTTP|error|refused|reset|timed|Closing" | head -16

echo
echo "======== 3) 只做 TCP 握手计时（验证是否慢）========"
for h in pypi.org mirrors.aliyun.com; do
  t=$(timeout 20 curl -4 -s -o /dev/null -w "connect=%{time_connect} total=%{time_total} code=%{http_code}" "https://$h/" 2>&1)
  echo "  $h: ${t:-（超时无输出）}"
done

echo
echo "======== 4) iptables 规则（mirrored 下 WSL 可能自带）========"
echo "--- filter INPUT ---"
iptables -L INPUT -n -v 2>/dev/null | head -12 || echo "  iptables 不可用"
echo "--- filter OUTPUT ---"
iptables -L OUTPUT -n -v 2>/dev/null | head -12 || true
echo "--- NAT ---"
iptables -t nat -L -n 2>/dev/null | head -8 || true

echo
echo "======== 5) nftables ========"
nft list ruleset 2>/dev/null | head -20 || echo "  nft 不可用/无规则"

echo
echo "======== 6) python urllib 测试（另一实现）========"
python3 - <<'PY' 2>&1 | head -12
import socket, urllib.request, ssl, sys
for url in ("https://pypi.org/simple/", "https://mirrors.aliyun.com/"):
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            print(f"  {url} -> HTTP {r.status}")
    except Exception as e:
        print(f"  {url} -> FAIL {type(e).__name__}: {e}")
# 纯 socket 测试
for host, port in (("pypi.org", 443), ("mirrors.aliyun.com", 443)):
    try:
        s = socket.create_connection((host, port), timeout=8)
        print(f"  socket {host}:{port} -> 连接成功 {s.getpeername()}")
        s.close()
    except Exception as e:
        print(f"  socket {host}:{port} -> FAIL {e}")
PY

echo
echo "STEP7-DONE"
