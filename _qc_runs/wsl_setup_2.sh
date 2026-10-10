#!/bin/bash
# WSL 重建 第 2 步：网络诊断（pip/apt/docker 都依赖网络）
set -u

echo "======== 1) DNS ========"
cat /etc/resolv.conf 2>/dev/null | head -5
echo "  解析 pypi.org: $(getent hosts pypi.org | head -1 || echo FAIL)"

echo
echo "======== 2) 逐个探测（带错误码）========"
for u in https://pypi.org/simple/ http://archive.ubuntu.com/ubuntu/ https://registry-1.docker.io/v2/ https://mirrors.aliyun.com/; do
  out=$(timeout 12 curl -s -o /dev/null -w "%{http_code} %{time_total}s" "$u" 2>&1)
  rc=$?
  printf '  rc=%-3s %-45s %s\n' "$rc" "$u" "${out:-（无响应）}"
done

echo
echo "======== 3) 详细错误（curl -v pypi）========"
timeout 15 curl -v -o /dev/null https://pypi.org/simple/ 2>&1 | head -14

echo
echo "======== 4) 代理环境 ========"
env | grep -iE "^(http_proxy|https_proxy|all_proxy|no_proxy)=" || echo "  (无代理环境变量)"
echo "  Windows 侧代理注册表:"
reg.exe query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable 2>/dev/null | tr -d '\0' | tail -2
reg.exe query "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer 2>/dev/null | tr -d '\0' | tail -2

echo
echo "======== 5) apt 是否可用（只测不装）========"
timeout 60 apt-get update -o Acquire::Retries=1 2>&1 | tail -6 || echo "  apt-get update 失败"

echo
echo "STEP2-DONE"
