#!/bin/bash
# 启动 G4 oracle 预检为持久 systemd service（不随调用会话结束而终止）
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
cat > /etc/systemd/system/g4-153.service <<'EOF'
[Unit]
Description=G4 oracle precheck FIN3-WKN-153
After=network-online.target docker.service

[Service]
Type=simple
Environment=HOME=/home/wff
Environment=LANG=C
Environment=PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONUTF8=1
ExecStart=/usr/bin/bash /mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs/g4_153_run.sh
Restart=no
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl reset-failed g4-153.service 2>/dev/null || true
systemctl start g4-153.service
sleep 20
echo "--- is-active ---"
systemctl is-active g4-153.service
echo "--- containers ---"
docker ps --format '{{.Names}} | {{.Status}}'
echo "--- log tail ---"
tail -3 "$Q/g4-153/oracle.log" 2>/dev/null
