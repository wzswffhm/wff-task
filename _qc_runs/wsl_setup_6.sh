#!/bin/bash
# WSL 重建 第 6 步：mirrored + firewall=false 下的干净网络测试
set -u

echo "======== 1) TCP 连通（脚本文件，无引号问题）========"
for tgt in "pypi.org 443" "mirrors.aliyun.com 443" "mirrors.tuna.tsinghua.edu.cn 443" "pypi.tuna.tsinghua.edu.cn 443"; do
  set -- $tgt
  if timeout 8 bash -c "exec 3<>/dev/tcp/$1/$2" 2>/dev/null; then
    echo "  $1:$2  可连"
  else
    echo "  $1:$2  不可连"
  fi
done

echo
echo "======== 2) curl 实测（公网）========"
code=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" https://pypi.org/simple/ 2>/dev/null)
echo "  pypi.org:    ${code:-失败}"
code=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" https://mirrors.aliyun.com/pypi/simple/ 2>/dev/null)
echo "  aliyun pypi: ${code:-失败}"
code=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" https://pypi.tuna.tsinghua.edu.cn/simple/ 2>/dev/null)
echo "  tuna pypi:   ${code:-失败}"

echo
echo "======== 3) 能解析吗（DNS）========"
for h in pypi.org mirrors.aliyun.com; do
  ip=$(getent ahostsv4 "$h" 2>/dev/null | head -1 | awk '{print $1}')
  echo "  $h -> ${ip:-解析失败}"
done

echo
echo "======== 4) 本机回环与网关 ========"
if timeout 5 bash -c "exec 3<>/dev/tcp/127.0.0.1/9" 2>/dev/null; then echo "  回环 9 可连"; else echo "  回环 9 不可连（正常，无服务）"; fi
gw=$(ip route | awk '/default/{print $3; exit}')
echo "  网关=$gw"
for p in 80 443 53; do
  if timeout 4 bash -c "exec 3<>/dev/tcp/$gw/$p" 2>/dev/null; then echo "    网关:$p 可连"; else echo "    网关:$p 不可连"; fi
done

echo
echo "======== 5) 内网可达性（公司 pypi 镜像常见位置）========"
for h in pypi.internal mirrors.internal nexus.company.com artifactory.company.com; do
  ip=$(getent ahostsv4 "$h" 2>/dev/null | head -1 | awk '{print $1}')
  [ -n "$ip" ] && echo "  $h -> $ip（可解析）" || true
done
echo "  (无输出=无这些主机)"

echo
echo "STEP6-DONE"
