#!/bin/bash
# 持久 systemd units：G5 v3 双模型
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

mk_unit() {  # $1=unit名 $2=模型
  cat > "/etc/systemd/system/$1" <<EOF
[Unit]
Description=G5 v3 $2 FIN3-WKN-152
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

mk_unit g5-v3-qwen.service qwen
mk_unit g5-v3-gpt.service gpt

systemctl daemon-reload
systemctl reset-failed g5-v3-qwen.service g5-v3-gpt.service 2>/dev/null || true
systemctl start g5-v3-qwen.service g5-v3-gpt.service
sleep 10
echo "--- G5 v3 状态 ---"
for s in g4-152v3 g5-v3-qwen g5-v3-gpt; do
  printf '  %-14s %s\n' "$s" "$(systemctl is-active $s.service)"
done
echo "--- 容器 ---"
docker ps --format '{{.Names}} | {{.Status}}'
