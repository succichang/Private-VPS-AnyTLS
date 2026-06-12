#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "请使用 root 用户运行。"
  exit 1
fi

RESET_DAY="${RESET_DAY:-$(date -u +%-d)}"
TOTAL_GB="${TOTAL_GB:-0}"
AGENT_URL="https://raw.githubusercontent.com/succichang/Private-VPS-Traffic/main/Private-VPS-Traffic-Agent.py"

case "$RESET_DAY" in
  ''|*[!0-9]*)
    echo "RESET_DAY 必须是 1-31 的数字。"
    exit 1
    ;;
esac
if (( RESET_DAY < 1 || RESET_DAY > 31 )); then
  echo "RESET_DAY 必须在 1-31 之间。"
  exit 1
fi
if ! [[ "$TOTAL_GB" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "TOTAL_GB 必须是数字，例如 500 或 1000。"
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl python3

install -d -m 0755 /usr/local/lib/private-vps-traffic
curl -fL --retry 3 \
  -o /usr/local/lib/private-vps-traffic/agent.py \
  "$AGENT_URL"
chmod 0755 /usr/local/lib/private-vps-traffic/agent.py

cat > /etc/systemd/system/private-vps-traffic.service <<EOF
[Unit]
Description=Private VPS traffic counter
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/lib/private-vps-traffic/agent.py
Restart=on-failure
RestartSec=5s
Environment=RESET_DAY=$RESET_DAY
Environment=TOTAL_GB=$TOTAL_GB
StateDirectory=private-vps-traffic
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/var/lib/private-vps-traffic

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now private-vps-traffic
sleep 1

systemctl is-active --quiet private-vps-traffic
curl -fsS http://127.0.0.1:18080/status >/dev/null

cat <<EOF
流量统计服务安装完成。
重置日：每月 $RESET_DAY 日（UTC）
套餐流量：${TOTAL_GB} GB（0 表示不显示配额）
监听地址：127.0.0.1:18080，仅可从 VPS 本机访问
EOF
