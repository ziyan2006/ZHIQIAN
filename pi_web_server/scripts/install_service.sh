#!/bin/bash
# ==============================================================================
# install_service.sh - 一键注册树莓派开机自启动服务
# ==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
  echo "❌ 请使用 sudo 权限运行此脚本: sudo bash $0"
  exit 1
fi

PROJECT_DIR=$(cd "$(dirname "$0")/.." && pwd)
CURRENT_USER=${SUDO_USER:-$(whoami)}
PYTHON_BIN=$(which python3)

echo "🔍 项目根目录: $PROJECT_DIR"
echo "🔍 运行用户:   $CURRENT_USER"
echo "🔍 Python路径: $PYTHON_BIN"

# 生成动态适配路径的 service 文件
SERVICE_FILE="/etc/systemd/system/pi-web.service"

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Raspberry Pi Smart Embedded Web Dashboard
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON_BIN $PROJECT_DIR/app.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "⚙️ 重新加载 systemd 配置..."
systemctl daemon-reload

echo "🚀 设置开机自启动并立即启动服务..."
systemctl enable pi-web.service
systemctl restart pi-web.service

echo "======================================================"
echo "✅ 树莓派 Web 控制台开机自启服务安装成功！"
echo "👉 查看状态: sudo systemctl status pi-web.service"
echo "👉 停止服务: sudo systemctl stop pi-web.service"
echo "👉 重启服务: sudo systemctl restart pi-web.service"
echo "======================================================"
