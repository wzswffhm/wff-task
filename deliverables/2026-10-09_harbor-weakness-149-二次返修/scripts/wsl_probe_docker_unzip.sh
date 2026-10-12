#!/usr/bin/env bash
echo "=== docker 镜像（找含 unzip/busybox 的小镜像）==="
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' 2>/dev/null | head -30
echo ""
echo "=== 现有镜像里哪个有 unzip/busybox ==="
for img in $(docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | head -8); do
  r=$(docker run --rm --entrypoint sh "$img" -c 'command -v unzip || command -v busybox || echo NONE' 2>/dev/null | tail -1)
  echo "  $img -> ${r:-N/A}"
done
echo ""
echo "=== 能否拉取 alpine（网络）==="
timeout 60 docker pull alpine:3.20 2>&1 | tail -3
echo "--- alpine 内 busybox unzip ---"
docker run --rm alpine:3.20 sh -c 'busybox unzip -v 2>&1 | head -2 || echo "no unzip applet"' 2>&1 | head -4
