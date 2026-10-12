#!/bin/bash
# 经 Windows 侧 pproxy 验证 WSL 出站连通性
GW=$(ip route | sed -n 's/^default via \([0-9.]*\).*/\1/p')
echo "GW=$GW"
export http_proxy="http://$GW:18080"
export https_proxy="http://$GW:18080"
export no_proxy="localhost,127.0.0.1,::1"
for u in https://pypi.org/simple/ https://registry-1.docker.io/v2/ https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com; do
  code=$(curl -s -o /dev/null -m 20 -w '%{http_code}' "$u")
  echo "$u -> ${code:-timeout}"
done
