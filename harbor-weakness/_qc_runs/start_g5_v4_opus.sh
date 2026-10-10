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
# 持久 systemd unit：G5 v4 opus（4router）
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
cat > /etc/systemd/system/g5-v4-opus.service <<EOF
[Unit]
Description=G5 v4 opus (4router) FIN3-WKN-152
After=network-online.target

[Service]
Type=simple
Environment=HOME=/home/wff
Environment=LANG=C
Environment=PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/bash $Q/g5_v3_opus_run.sh
Restart=no
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl reset-failed g5-v4-opus.service 2>/dev/null || true
systemctl start g5-v4-opus.service
sleep 10
echo "--- G5 v4 全部 service ---"
for s in g5-v4-qwen g5-v4-gpt g5-v4-opus; do printf '  %-12s %s\n' "$s" "$(systemctl is-active $s.service)"; done
echo "--- 容器 ---"
docker ps --format '{{.Names}} | {{.Status}}'
