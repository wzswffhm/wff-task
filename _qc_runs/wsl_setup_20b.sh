#!/bin/bash
set -u
GW=$(ip route | awk '/^default/{print $3; exit}')
PROXY="http://$GW:18080"
echo "网关=$GW"
# docker 代理配置：root 与 wff 两处都要（跑分脚本 HOME=/home/wff）
for d in /root/.docker /home/wff/.docker; do
  mkdir -p "$d"
  cat > "$d/config.json" <<EOF
{
  "proxies": {
    "default": {
      "httpProxy": "$PROXY",
      "httpsProxy": "$PROXY",
      "noProxy": "localhost,127.0.0.1"
    }
  }
}
EOF
  chmod 644 "$d/config.json"
  echo "  [OK] $d/config.json"
done
# 确保 wff 拥有
chown -R wff:wff /home/wff/.docker 2>/dev/null || true
# daemon systemd 代理同样刷新（写绝对当前网关）
mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/proxy.conf <<EOF
[Service]
Environment="HTTP_PROXY=$PROXY"
Environment="HTTPS_PROXY=$PROXY"
Environment="NO_PROXY=localhost,127.0.0.1"
EOF
systemctl daemon-reload 2>/dev/null || true
echo "  [OK] docker.service.d/proxy.conf"
echo
echo "--- 校验（模拟 HOME=/home/wff）---"
env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/home/wff bash -c 'cat $HOME/.docker/config.json 2>/dev/null | head -6'
echo "--- 当前 pproxy 连接（WSL 侧）---"
ss -tn 2>/dev/null | grep 18080 | head -4 || netstat -tn 2>/dev/null | grep 18080 | head -4
echo "STEP20B-DONE"