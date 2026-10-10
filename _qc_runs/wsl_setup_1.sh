#!/bin/bash
# WSL Ubuntu 重建后环境搭建 第 1 步：体检 + 建 wff 用户
set -u

echo "======== 1) 基础体检 ========"
echo "USER=$(whoami)"
if [ -f /etc/os-release ]; then . /etc/os-release; echo "OS=${PRETTY_NAME}"; fi
for c in python3 pip3 git curl wget useradd systemctl; do
  p=$(command -v "$c" 2>/dev/null || true)
  printf '  %-10s %s\n' "$c" "${p:-MISSING}"
done
echo "  python3 -> $(python3 --version 2>&1 || echo n/a)"
df -h / | tail -1
echo "  内存: $(free -h | awk '/^Mem:/{print $2" total, "$7" avail"}')"

echo
echo "======== 2) 网络探测 ========"
timeout 10 curl -sI https://pypi.org/simple/ | head -1 || echo "  pypi 不可达"
timeout 10 curl -sI https://registry-1.docker.io/v2/ | head -1 || echo "  docker hub 不可达"
timeout 10 curl -sI http://archive.ubuntu.com/ubuntu/ | head -1 || echo "  ubuntu 源不可达"

echo
echo "======== 3) 创建 wff 用户（跑分脚本 HOME=/home/wff）========"
if id wff >/dev/null 2>&1; then
  echo "  用户已存在"
else
  useradd -m -s /bin/bash wff
  echo "wff ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/wff
  chmod 0440 /etc/sudoers.d/wff
  echo "  已创建并授权 sudo"
fi
ls -ld /home/wff

echo
echo "======== 4) Windows 侧资源可达性（/mnt/c）========"
ls -d /mnt/c/Users/Administrator/Desktop/wff-task 2>/dev/null && echo "  workspace 可达" || echo "  workspace 不可达"
ls /mnt/c/Users/Administrator/.wff-creds/judge.env >/dev/null 2>&1 && echo "  judge.env 可达" || echo "  judge.env 不可达"
grep -c . /mnt/c/Users/Administrator/.wff-creds/judge.env 2>/dev/null | xargs -I{} echo "  judge.env 行数: {}"

echo
echo "======== 5) WSL 配置（wsl.conf）========"
cat /etc/wsl.conf 2>/dev/null || echo "  (无 wsl.conf)"

echo
echo "STEP1-DONE"
