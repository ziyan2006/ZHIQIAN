#!/bin/bash
# ==============================================================================
# setup_hotspot.sh - 树莓派 3B+ 板载 WiFi 一键开启独立 AP 热点脚本
# 支持系统: Raspberry Pi OS (Bookworm / Bullseye)
# 热点名称 (SSID): Pi-SmartLab
# 热点密码: raspberry123
# 网关 IP: 192.168.4.1
# ==============================================================================

set -e

HOTSPOT_SSID="Pi-SmartLab"
HOTSPOT_PASS="raspberry123"
HOTSPOT_IP="192.168.4.1/24"
CON_NAME="Pi-Hotspot"

echo "======================================================"
echo "📡 开始配置树莓派 3B+ 板载独立 AP 热点..."
echo "======================================================"

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
  echo "❌ 请使用 sudo 权限运行此脚本: sudo bash $0"
  exit 1
fi

# 检查是否安装 NetworkManager (nmcli)
if command -v nmcli >/dev/null 2>&1; then
    echo "🔍 检测到 NetworkManager 网络管理服务 (现代树莓派 OS Bookworm 默认)..."
    
    # 停止旧连接 (若存在)
    nmcli con delete "$CON_NAME" 2>/dev/null || true

    echo "⚙️ 正在创建 WiFi 热点: SSID=$HOTSPOT_SSID ..."
    nmcli con add type wifi ifname wlan0 con-name "$CON_NAME" autoconnect yes ssid "$HOTSPOT_SSID"
    
    echo "🔒 配置 WPA2 认证与热点频段..."
    nmcli con modify "$CON_NAME" 802-11-wireless.mode ap 802-11-wireless.band bg
    nmcli con modify "$CON_NAME" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$HOTSPOT_PASS"
    
    echo "🌐 分配固定子网 IP: 192.168.4.1 (自动启用内置 DHCP 服务)..."
    nmcli con modify "$CON_NAME" ipv4.method shared ipv4.addresses "$HOTSPOT_IP"
    
    echo "🚀 启动热点..."
    nmcli con up "$CON_NAME"

else
    echo "🔍 未检测到 nmcli，采用 hostapd + dnsmasq 经典方案 (适用于 Bullseye/Buster)..."
    
    # 安装依赖
    apt-get update -y
    apt-get install -y hostapd dnsmasq rfkill

    rfkill unblock wlan || true

    # 停止默认服务
    systemctl stop hostapd || true
    systemctl stop dnsmasq || true

    # 配置 dhcpcd 静态 IP
    if [ -f /etc/dhcpcd.conf ]; then
        if ! grep -q "interface wlan0" /etc/dhcpcd.conf; then
            cat <<EOF >> /etc/dhcpcd.conf

# 树莓派独立热点静态 IP
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF
        fi
    fi

    # 配置 dnsmasq (DHCP 分配 192.168.4.2 ~ 192.168.4.50)
    mv /etc/dnsmasq.conf /etc/dnsmasq.conf.bak 2>/dev/null || true
    cat <<EOF > /etc/dnsmasq.conf
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.50,255.255.255.0,24h
domain=local
address=/pi.local/192.168.4.1
EOF

    # 配置 hostapd
    cat <<EOF > /etc/hostapd/hostapd.conf
interface=wlan0
driver=nl80211
ssid=$HOTSPOT_SSID
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$HOTSPOT_PASS
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

    sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|g' /etc/default/hostapd 2>/dev/null || true

    systemctl unmask hostapd
    systemctl enable hostapd
    systemctl restart dhcpcd
    systemctl restart dnsmasq
    systemctl restart hostapd
fi

echo "======================================================"
echo "✅ 树莓派独立 AP 热点已成功建立并开启！"
echo "------------------------------------------------------"
echo "📱 手机/电脑请连接 WiFi: $HOTSPOT_SSID"
echo "🔑 WiFi 密码:          $HOTSPOT_PASS"
echo "🌐 树莓派网关 IP:       192.168.4.1"
echo "👉 打开浏览器访问:      http://192.168.4.1:5000"
echo "👉 或直接域名访问:      http://pi.local:5000"
echo "======================================================"
