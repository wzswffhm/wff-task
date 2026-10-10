#!/bin/bash

# --- WSL 出站必须走 Windows 侧 pproxy（本环境无直连 TCP）---
GW=$(ip route 2>/dev/null | awk "/^default/{print \$3; exit}")
if [ -n "${GW:-}" ]; then
  export http_proxy="http://$GW:18080" https_proxy="http://$GW:18080"
  export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
  export no_proxy="localhost,127.0.0.1,::1"
fi
unset GW
# --- end proxy ---
# 持久 systemd units：G5 v4 双模型
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

mk_unit() {  # $1=unit名 $2=模型
  cat > "/etc/systemd/system/$1" <<EOF
[Unit]
Description=G5 v4 $2 FIN3-WKN-152
After=network-online.target

[Service]
Type=simple
Environment=HOME=/home/wff
Environment=LANG=C
Environment=PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/bash $Q/g5_v3_run.sh $2
Restart=no
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
}

mk_unit g5-v4-qwen.service qwen
mk_unit g5-v4-gpt.service gpt

systemctl daemon-reload
systemctl reset-failed g5-v4-qwen.service g5-v4-gpt.service 2>/dev/null || true
systemctl start g5-v4-qwen.service g5-v4-gpt.service
sleep 10
echo "--- G5 v4 状态 ---"
for s in g4-152v4 g5-v4-qwen g5-v4-gpt; do
  printf '  %-14s %s\n' "$s" "$(systemctl is-active $s.service)"
done
echo "--- 容器 ---"
docker ps --format '{{.Names}} | {{.Status}}'
