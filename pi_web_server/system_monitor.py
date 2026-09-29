"""
system_monitor.py - 树莓派底层硬件与系统状态采集模块
支持在树莓派 Linux 硬件上直接读取真实物理指标，
并在 Windows PC 本地调试环境下提供智能模拟回退。
"""

import os
import time
import socket
import platform
import psutil

# 记录应用启动时间
START_TIME = time.time()


def get_cpu_temperature() -> float:
    """
    获取 CPU 核心温度 (单位: 摄氏度)
    在树莓派 Linux 下读取 /sys/class/thermal/thermal_zone0/temp
    若在开发调试环境 (如 Windows) 则返回模拟稳定温度
    """
    temp_path = "/sys/class/thermal/thermal_zone0/temp"
    if os.path.exists(temp_path):
        try:
            with open(temp_path, "r", encoding="utf-8") as f:
                temp_raw = f.read().strip()
                return round(float(temp_raw) / 1000.0, 1)
        except Exception:
            pass

    # 仅在 Linux 下尝试 vcgencmd
    if platform.system() == "Linux":
        try:
            with os.popen("vcgencmd measure_temp") as pipe:
                res = pipe.readline()
                if "temp=" in res:
                    return float(res.replace("temp=", "").replace("'C\n", "").strip())
        except Exception:
            pass

    # Windows / 非树莓派开发环境回退模拟数据 (42.0 ~ 45.0 之间微小浮动)
    import math
    simulated = 43.5 + 1.2 * math.sin(time.time() / 5.0)
    return round(simulated, 1)


def get_ip_address() -> str:
    """获取本机当前主 IP 地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 连接一个不需要实际可达的公网 IP 获取选路网卡 IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.4.1"  # 热点默认 IP


def format_uptime(seconds: float) -> str:
    """将秒数格式化为人类可读的运行时长"""
    seconds = int(seconds)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if days > 0:
        return f"{days}天 {hours}时 {minutes}分"
    if hours > 0:
        return f"{hours}时 {minutes}分 {secs}秒"
    return f"{minutes}分 {secs}秒"


def get_connected_clients_count() -> int:
    """
    检测连接到树莓派热点的客户端数量
    检查 dnsmasq 或 NetworkManager 租约文件
    """
    lease_paths = [
        "/var/lib/misc/dnsmasq.leases",
        "/var/lib/NetworkManager/dnsmasq-wlan0.leases",
    ]
    for lp in lease_paths:
        if os.path.exists(lp):
            try:
                with open(lp, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                    return max(1, len(lines))
            except Exception:
                pass
    return 1


def get_full_system_status() -> dict:
    """采集并组装系统全量状态数据"""
    cpu_usage = psutil.cpu_percent(interval=None)
    cpu_freq = psutil.cpu_freq()
    freq_mhz = int(cpu_freq.current) if cpu_freq else 1400

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    boot_time = psutil.boot_time()
    system_uptime = time.time() - boot_time
    server_uptime = time.time() - START_TIME

    return {
        "status": "online",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": {
            "system": platform.system(),
            "node": platform.node(),
            "release": platform.release(),
            "machine": platform.machine(),
            "is_raspberry_pi": os.path.exists("/sys/class/thermal/thermal_zone0/temp"),
        },
        "network": {
            "ip": get_ip_address(),
            "hotspot_ip": "192.168.4.1",
            "hostname": "pi.local",
            "clients_count": get_connected_clients_count(),
        },
        "cpu": {
            "usage_percent": cpu_usage,
            "core_count": psutil.cpu_count(logical=True),
            "freq_mhz": freq_mhz,
            "temperature_c": get_cpu_temperature(),
        },
        "memory": {
            "total_mb": round(mem.total / (1024 * 1024), 1),
            "used_mb": round(mem.used / (1024 * 1024), 1),
            "free_mb": round(mem.available / (1024 * 1024), 1),
            "percent": mem.percent,
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 1),
            "used_gb": round(disk.used / (1024**3), 1),
            "free_gb": round(disk.free / (1024**3), 1),
            "percent": disk.percent,
        },
        "uptime": {
            "system": format_uptime(system_uptime),
            "server": format_uptime(server_uptime),
        },
    }
