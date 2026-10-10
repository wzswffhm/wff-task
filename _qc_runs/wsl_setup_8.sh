#!/bin/bash
# WSL 重建 第 8 步：路由对比 + 镜像源可用性 + 模型端点可达性（跑分必需）
set -u

echo "======== 1) 路由对比（pypi 不可达 vs aliyun 可达）========"
for ip in 151.101.0.223 14.29.48.35 183.60.240.57; do
  r=$(ip route get "$ip" 2>&1 | head -1)
  echo "  $ip -> $r"
done

echo
echo "======== 2) 完整路由表 ========"
ip route show table all 2>/dev/null | head -20

echo
echo "======== 3) aliyun 镜像实际可用性（带 UA 与正确路径）========"
for u in "https://mirrors.aliyun.com/pypi/simple/pip/" "https://mirrors.cloud.aliyuncs.com/pypi/simple/pip/" "https://mirrors.aliyun.com/ubuntu/dists/jammy/Release"; do
  code=$(timeout 20 curl -4 -s -A "pip/26.1" -o /dev/null -w "%{http_code}" "$u" 2>/dev/null)
  echo "  ${code:-失败}  $u"
done

echo
echo "======== 4) 其他国内镜像 ========"
for u in "https://pypi.tuna.tsinghua.edu.cn/simple/pip/" "https://mirrors.ustc.edu.cn/pypi/simple/pip/" "https://repo.huaweicloud.com/repository/pypi/simple/pip/"; do
  code=$(timeout 15 curl -4 -s -A "pip/26.1" -o /dev/null -w "%{http_code}" "$u" 2>/dev/null)
  echo "  ${code:-失败}  $u"
done

echo
echo "======== 5) 模型/判官端点可达性（跑分必需，最关键）========"
for u in "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com" \
         "https://fanrenapi.com" \
         "https://4router.net" \
         "https://registry.npmjs.org" \
         "https://github.com"; do
  code=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code} t=%{time_total}" "$u" 2>/dev/null)
  echo "  ${code:-失败/超时}  $u"
done

echo
echo "======== 6) DNS 与 IPv6（pypi 是否有可用地址）========"
echo "  pypi.org A:"; getent ahostsv4 pypi.org | head -4
echo "  pypi.org 是否有其他镜像可达:"
code=$(timeout 15 curl -4 -s -A "pip/26.1" -o /dev/null -w "%{http_code}" "https://mirrors.aliyun.com/pypi/simple/" 2>/dev/null)
echo "    aliyun pypi simple: ${code:-失败}"

echo
echo "STEP8-DONE"
