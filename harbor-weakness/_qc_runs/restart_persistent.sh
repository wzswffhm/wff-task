#!/bin/bash
# 用持久 systemd service（非 systemd-run 瞬时 unit）重启 G5 两个模型跑分。
# 根因：systemd-run --collect 的瞬时 unit 会随 wsl.exe 会话结束被 stop（journal 20:11:23 实证）。
set -u
Q=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs

# 1) 输出到全新目录，保留被中断试次的证据
sed -i 's#_qc_runs/g5-152v2-qwen#_qc_runs/g5-152v2-qwen2#g; s#--trial-name qwen38max-152v2#--trial-name qwen38max2-152v2#g' "$Q/g5_qwen_run.sh"
sed -i 's#_qc_runs/g5-152v2-gpt3#_qc_runs/g5-152v2-gpt4#g; s#--trial-name gpt56sol3-152v2#--trial-name gpt56sol4-152v2#g' "$Q/g5_gpt_run.sh"

echo "--- 已更新输出目录 ---"
grep -nE 'OUT=|trial-name' "$Q/g5_qwen_run.sh" "$Q/g5_gpt_run.sh"

# 2) 写入持久 service 文件
write_service() {
  local name="$1" desc="$2" script="$3"
  cat > "/etc/systemd/system/${name}.service" <<EOF
[Unit]
Description=${desc}
After=network-online.target

[Service]
Type=simple
Environment=HOME=/home/wff
Environment=LANG=C
Environment=PATH=/home/wff/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/bash ${script}
Restart=no
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
  echo "wrote /etc/systemd/system/${name}.service"
}

write_service g5-qwen-152v2 "G5 qwen3.8-max-0902 FIN3-WKN-152" "$Q/g5_qwen_run.sh"
write_service g5-gpt-152v2  "G5 gpt-5.6-sol FIN3-WKN-152"     "$Q/g5_gpt_run.sh"

# 3) 启动
systemctl daemon-reload
systemctl reset-failed g5-qwen-152v2.service g5-gpt-152v2.service 2>/dev/null
systemctl start g5-qwen-152v2.service
systemctl start g5-gpt-152v2.service
sleep 8
echo
echo "--- service 状态 ---"
systemctl is-active g5-qwen-152v2.service g5-gpt-152v2.service
echo
echo "--- 容器 ---"
docker ps --format '{{.Names}} | {{.Status}}'
