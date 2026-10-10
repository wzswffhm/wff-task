#!/bin/bash
# 环境就绪最终验收（跑分前的完整体检）
set -u
PASS=0; FAIL=0
ok()  { echo "  [OK]   $1"; PASS=$((PASS+1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }

echo "==================== 1) 网络（经 Windows pproxy）===================="
GW=$(ip route 2>/dev/null | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:18080" https_proxy="http://$GW:18080" no_proxy="localhost,127.0.0.1"
echo "  网关=$GW"
for t in "https://pypi.org/simple/|pypi" \
         "https://fanrenapi.com|gpt-5.6-sol 端点" \
         "https://4router.net|claude-opus-4-8 端点" \
         "https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com|qwen+判官端点" \
         "https://registry.npmjs.org/|npm"; do
  url="${t%%|*}"; name="${t##*|}"
  code=$(timeout 25 curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
  if [ -n "$code" ] && [ "$code" != "000" ]; then ok "$name http=$code"; else bad "$name"; fi
done

echo
echo "==================== 2) 运行时组件 ===================="
v=$(python3.13 --version 2>&1 | awk '{print $2}')
[ -n "$v" ] && ok "python3.13 = $v" || bad "python3.13"
v=$(python3.13 -m pip --version 2>&1 | awk '{print $2}')
[ -n "$v" ] && ok "pip = $v" || bad "pip"
v=$(/usr/local/bin/harbor --version 2>&1 | head -1)
[ -n "$v" ] && ok "harbor = $v" || bad "harbor"
/usr/local/bin/harbor trial start --help >/dev/null 2>&1 && ok "harbor trial start 子命令可用" || bad "harbor trial start"
if command -v docker >/dev/null 2>&1; then
  v=$(docker --version 2>&1 | awk '{print $3}')
  st=$(systemctl is-active docker 2>/dev/null)
  [ "$st" = "active" ] && ok "docker = $v (service active)" || bad "docker service = $st"
else
  bad "docker 未安装"
fi
systemctl is-active wsl-proxy-refresh >/dev/null 2>&1 && ok "网关自愈服务 enabled" || echo "  [SKIP] 自愈服务（oneshot 已执行过则正常）"

echo
echo "==================== 3) 用户与凭据 ===================="
id wff >/dev/null 2>&1 && ok "wff 用户" || bad "wff 用户"
[ -f /mnt/c/Users/Administrator/.wff-creds/judge.env ] && ok "judge.env ($(grep -c . /mnt/c/Users/Administrator/.wff-creds/judge.env) 行)" || bad "judge.env"
for k in JUDGE_API_KEY JUDGE_BASE_URL JUDGE_MODEL; do
  grep -q "^$k=" /mnt/c/Users/Administrator/.wff-creds/judge.env 2>/dev/null && ok "judge.env 含 $k" || bad "judge.env 缺 $k"
done

echo
echo "==================== 4) 题包与 v4 脚本 ===================="
T=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/FIN3-WKN-152
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
[ -f "$T/task.toml" ] && ok "task.toml ($(grep -o 'version = \"[^\"]*\"' $T/task.toml | head -1))" || bad "task.toml"
[ -f "$T/tests/rubrics.toml" ] && ok "rubrics.toml ($(grep -c '^\[\[criterion\]\]' $T/tests/rubrics.toml) 条判据)" || bad "rubrics.toml"
[ -f "$T/instruction.md" ] && ok "instruction.md" || bad "instruction.md"
[ -f "$T/solution/golden_output/FIN3-WKN-152_reproduce.py" ] && ok "金标 reproduce.py" || bad "金标"
for s in g4_v4_run.sh g5_v4_run.sh g5_v4_opus_run.sh start_g4_v4.sh; do
  [ -f "$Q/$s" ] && ok "跑分脚本 $s" || bad "跑分脚本 $s"
done

echo
echo "==================== 5) 镜像 ===================="
if docker images 2>/dev/null | grep -q "fin3-wkn-152"; then
  ok "fin3-wkn-152 镜像: $(docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | grep fin3-wkn-152)"
else
  bad "fin3-wkn-152 镜像缺失（构建中或需构建）"
fi

echo
echo "==================== 6) 代理自启（Windows 侧）===================="
echo "  （由 Windows 侧确认：计划任务 WSL-Proxy-18080）"

echo
echo "=========================================="
echo "  WSL 侧结果: PASS=$PASS  FAIL=$FAIL"
[ "$FAIL" -eq 0 ] && echo "  ✅ WSL 环境就绪" || echo "  ⚠️  仍有 $FAIL 项未就绪"
echo "=========================================="
