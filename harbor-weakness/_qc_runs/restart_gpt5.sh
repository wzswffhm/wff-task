#!/bin/bash
# gpt 第 5 轮重跑（独立 service，不影响正在判分的 gpt4）
set -u
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

sed 's#_qc_runs/g5-152v2-gpt4#_qc_runs/g5-152v2-gpt5#g; s#--trial-name gpt56sol4-152v2#--trial-name gpt56sol5-152v2#g' \
  "$Q/g5_gpt_run.sh" > "$Q/g5_gpt5_run.sh"
chmod +x "$Q/g5_gpt5_run.sh"

echo "--- 新脚本关键行 ---"
grep -nE 'OUT=|trial-name|ANTHROPIC_BASE_URL|ANTHROPIC_MODEL' "$Q/g5_gpt5_run.sh"

cat > /etc/systemd/system/g5-gpt5-152v2.service <<EOF
[Unit]
Description=G5 gpt-5.6-sol FIN3-WKN-152 round5 retry
After=network-online.target

[Service]
Type=simple
Environment=HOME=/home/wff
Environment=LANG=C
Environment=PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/bash $Q/g5_gpt5_run.sh
Restart=no
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl reset-failed g5-gpt5-152v2.service 2>/dev/null
systemctl start g5-gpt5-152v2.service
sleep 10
echo
echo "--- 状态 ---"
systemctl is-active g5-gpt5-152v2.service g5-qwen-152v2.service g5-gpt-152v2.service
echo
docker ps --format '{{.Names}} | {{.Status}}'
