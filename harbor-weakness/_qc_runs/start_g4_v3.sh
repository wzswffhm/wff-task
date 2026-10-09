#!/bin/bash
# 持久 systemd unit：G4 oracle v3
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
cat > /etc/systemd/system/g4-152v3.service <<EOF
[Unit]
Description=G4 oracle FIN3-WKN-152 v3
After=network-online.target

[Service]
Type=simple
Environment=HOME=/home/wff
Environment=LANG=C
Environment=PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/bash $Q/g4_v3_run.sh
Restart=no
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl reset-failed g4-152v3.service 2>/dev/null || true
systemctl start g4-152v3.service
sleep 8
echo "--- g4-152v3 状态 ---"
systemctl is-active g4-152v3.service
echo "--- 当前全部容器 ---"
docker ps --format '{{.Names}} | {{.Status}}'
echo "--- 当前全部 g5/g4 service ---"
systemctl is-active g5-qwen-152v2.service g5-gpt-152v2.service g5-gpt5-152v2.service g4-152v3.service
