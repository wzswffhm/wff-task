#!/bin/bash
# FIN3-WKN-153 环境探测（只读，不启动任何容器）
echo "=== gateway ==="
ip route | sed -n 's/^default via \([0-9.]*\).*/GW=\1/p'
echo "=== images ==="
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | head -10
echo "=== containers ==="
docker ps --format '{{.Names}} | {{.Status}}'
echo "=== judge host reachability (direct) ==="
curl -s -o /dev/null -m 12 -w 'direct_https_code=%{http_code}\n' https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com 2>&1 || echo "direct curl failed rc=$?"
echo "=== pypi reachability (direct) ==="
curl -s -o /dev/null -m 12 -w 'pypi_code=%{http_code}\n' https://pypi.org/simple/ 2>&1 || echo "pypi curl failed rc=$?"
echo "=== docker registry reachability ==="
curl -s -o /dev/null -m 12 -w 'registry_code=%{http_code}\n' https://registry-1.docker.io/v2/ 2>&1 || echo "registry curl failed rc=$?"
echo "=== harbor version ==="
harbor --version 2>&1 | head -1
echo "=== free resources ==="
free -g | head -2
nproc
