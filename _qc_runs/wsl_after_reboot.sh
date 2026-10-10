#!/bin/bash
# 重启电脑后：一键验证 WSL 环境与网络是否就绪
# 用法（Windows 侧）:
#   wsl -d Ubuntu-22.04 -u root -- bash /mnt/c/Users/Administrator/Desktop/wff-task/_qc_runs/wsl_after_reboot.sh
set -u
PASS=0; FAIL=0
ok()   { echo "  [OK]   $1"; PASS=$((PASS+1)); }
bad()  { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }

echo "==================== 1) 系统与用户 ===================="
. /etc/os-release 2>/dev/null
echo "  OS=${PRETTY_NAME:-?}  kernel=$(uname -r)"
id wff >/dev/null 2>&1 && ok "wff 用户存在" || bad "wff 用户缺失"
[ -d /home/wff ] && ok "/home/wff 存在" || bad "/home/wff 缺失"
command -v systemctl >/dev/null && ok "systemctl 可用 ($(systemctl is-system-running 2>/dev/null || echo ?))" || bad "systemctl 缺失"
command -v python3 >/dev/null && ok "python3 $(python3 --version 2>&1 | awk '{print $2}')" || bad "python3 缺失"

echo
echo "==================== 2) 接口与路由 ===================="
ip -br link | grep -v lo | while read -r l; do echo "    $l"; done
defdev=$(ip route 2>/dev/null | awk '/^default/{print $5; exit}')
defgw=$(ip route 2>/dev/null | awk '/^default/{print $3; exit}')
state=$(ip -br link | awk -v d="$defdev" '$1==d{print $2}')
if [ -n "$defdev" ] && [ "$state" = "UP" ]; then
  ok "默认路由 via $defgw dev $defdev (state=UP)"
else
  bad "默认路由异常: via ${defgw:-无} dev ${defdev:-无} state=${state:-无}"
fi

echo
echo "==================== 3) 出站 TCP（决定性）===================="
declare -a TARGETS=(
  "https://pypi.org/simple/|pip 源"
  "https://mirrors.aliyun.com/ubuntu/dists/jammy/Release|apt 阿里云源"
  "https://fanrenapi.com|gpt-5.6-sol 端点"
  "https://4router.net|claude-opus-4-8 端点"
  "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com|qwen+判官端点"
  "https://registry.npmjs.org/|npm 源"
)
for t in "${TARGETS[@]}"; do
  url="${t%%|*}"; name="${t##*|}"
  code=$(timeout 20 curl -4 -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
  if [ -n "$code" ] && [ "$code" != "000" ]; then
    ok "$name  http=$code"
  else
    bad "$name  ($url)"
  fi
done

echo
echo "==================== 4) 依赖就绪 ===================="
WHEELS=/mnt/c/Users/Administrator/Desktop/wff-task/_qc_runs/wsl_wheels
n=$(ls "$WHEELS"/*.whl 2>/dev/null | wc -l)
[ "$n" -gt 0 ] && ok "离线 wheel 包 $n 个（供 pip 离线安装）" || bad "离线 wheel 缺失"
command -v docker >/dev/null && ok "docker 客户端 $(docker --version 2>&1 | head -c 60)" || bad "docker 未安装"
command -v harbor >/dev/null && ok "harbor $(harbor --version 2>&1 | head -c 40)" || bad "harbor 未安装"
python3 -m pip --version >/dev/null 2>&1 && ok "pip 可用" || bad "pip 缺失（python3-pip 未装）"

echo
echo "==================== 5) Windows 侧资源 ===================="
[ -d /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/FIN3-WKN-152 ] && ok "题包可达" || bad "题包不可达"
[ -f /mnt/c/Users/Administrator/.wff-creds/judge.env ] && ok "judge.env 可达" || bad "judge.env 不可达"
[ -d /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g4_v4_run.sh ] || \
  [ -f /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g4_v4_run.sh ] && ok "v4 跑分脚本在" || bad "v4 跑分脚本缺失"

echo
echo "=========================================="
echo "  结果: PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "  环境就绪 —— 可以开始跑分（但按指示：先通知，不自动跑）"
else
  echo "  仍有 $FAIL 项未就绪"
fi
echo "=========================================="
