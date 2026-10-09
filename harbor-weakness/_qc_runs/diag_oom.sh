#!/bin/bash
# 中断根因诊断：OOM / 引擎重启
echo "=== 内存 ==="
free -m
echo
echo "=== dmesg 末尾（找 oom-kill / docker） ==="
dmesg 2>/dev/null | tail -40 | grep -iE 'oom|kill|docker|memory' || dmesg 2>/dev/null | tail -20
echo
echo "=== docker 引擎是否存活 ==="
docker info --format '{{.ServerVersion}} / {{.OperatingSystem}} / containers={{.Containers}}' 2>&1 | head -3
echo
echo "=== docker 事件（最近 200 条中的 die/destroy/oom） ==="
timeout 6 docker events --since 40m --until 0s --filter 'event=die' --filter 'event=oom' --filter 'event=destroy' --format '{{.Time}} {{.Action}} {{.Actor.Attributes.name}}' 2>&1 | tail -25
echo
echo "=== Docker Desktop 进程（Windows 侧不可见，这里看 WSL 侧 dockerd） ==="
ps -eo pid,etime,rss,args --no-headers | grep -E 'dockerd|containerd' | grep -v grep | head -5
echo
echo "=== 当前时间 ==="
date '+%F %T'
