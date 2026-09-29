#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键自动将 MoveNet 人体骨骼识别算法、模型权重、依赖库与升级后的 Web 控制台同步部署至树莓派 3B+
"""

import os
import sys
import time
import socket
import paramiko

BASE_DIR = r"d:\Codex\智嵌\pi_web_server"

FILES_TO_UPLOAD = [
    (os.path.join(BASE_DIR, "app.py"), "/home/superboy/pi_web_server/app.py"),
    (os.path.join(BASE_DIR, "pose_detector.py"), "/home/superboy/pi_web_server/pose_detector.py"),
    (os.path.join(BASE_DIR, "templates", "index.html"), "/home/superboy/pi_web_server/templates/index.html"),
    (os.path.join(BASE_DIR, "static", "js", "dashboard.js"), "/home/superboy/pi_web_server/static/js/dashboard.js"),
    (os.path.join(BASE_DIR, "models", "movenet_lightning_int8.tflite"), "/home/superboy/pi_web_server/models/movenet_lightning_int8.tflite"),
    (os.path.join(BASE_DIR, "models", "tflite_runtime-2.16.1-cp311-none-linux_aarch64.whl"), "/home/superboy/pi_web_server/models/tflite_runtime-2.16.1-cp311-none-linux_aarch64.whl"),
]

def try_connect():
    for h in ["superboy-2.local", "192.168.4.1"]:
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(h, port=22, username="superboy", password="raspberry", timeout=2)
            print(f"[+] 成功通过目标地址 [{h}] 建立 SSH 连接！")
            return client
        except Exception:
            pass

    try:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock.settimeout(2.5)
        sock.connect(('fe80::ba27:ebff:fea2:3b45', 22, 0, 10))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect('fe80::ba27:ebff:fea2:3b45', port=22, username="superboy", password="raspberry", sock=sock)
        print("[+] 成功通过 IPv6 直连链路建立 SSH 连接！")
        return client
    except Exception:
        pass

    return None

def deploy():
    print("==================================================")
    print("[*] 开始向树莓派 3B+ 部署 MoveNet 人体骨骼识别系统...")
    print("==================================================")

    client = None
    for attempt in range(1, 15):
        client = try_connect()
        if client:
            break
        print(f"[-] 尝试连接树莓派 ({attempt}/15)... 等待网络重连中")
        time.sleep(2)

    if not client:
        print("[!] 无法建立连接，请检查网线连接。")
        return False

    try:
        # 1. 创建远程目录
        stdin, stdout, stderr = client.exec_command("mkdir -p /home/superboy/pi_web_server/models")
        stdout.channel.recv_exit_status()

        # 2. 上传文件
        sftp = client.open_sftp()
        for local_p, remote_p in FILES_TO_UPLOAD:
            if not os.path.exists(local_p):
                print(f"[!] 警告：本地文件不存在，跳过: {local_p}")
                continue
            file_size_mb = os.path.getsize(local_p) / (1024 * 1024)
            print(f"[*] 正在上传: {os.path.basename(local_p)} ({file_size_mb:.2f} MB) -> {remote_p} ...")
            sftp.put(local_p, remote_p)
            print(f"[+] 上传完成: {os.path.basename(local_p)}")
        sftp.close()

        # 3. 安装 tflite_runtime 运行环境 (如果尚未安装)
        print("[*] 检查并配置 tflite-runtime 运行环境...")
        install_cmd = """python3 -c "import tflite_runtime" 2>/dev/null || python3 -m pip install /home/superboy/pi_web_server/models/tflite_runtime-2.16.1-cp311-none-linux_aarch64.whl --break-system-packages"""
        stdin, stdout, stderr = client.exec_command(install_cmd)
        exit_code = stdout.channel.recv_exit_status()
        print(f"[+] tflite-runtime 检查/安装完成 (Exit: {exit_code})")
        print(stdout.read().decode())

        # 4. 重启 pi-web.service 服务
        print("[*] 正在重启 pi-web.service 服务以加载骨骼识别引擎...")
        restart_cmd = "echo raspberry | sudo -S systemctl restart pi-web.service"
        stdin, stdout, stderr = client.exec_command(restart_cmd)
        stdout.channel.recv_exit_status()
        time.sleep(1.5)

        # 5. 校验服务运行状态
        status_cmd = "systemctl is-active pi-web.service"
        stdin, stdout, stderr = client.exec_command(status_cmd)
        service_state = stdout.read().decode().strip()
        print(f"[+] 服务状态: {service_state}")

        if service_state == "active":
            print("==================================================")
            print("[SUCCESS] 恭喜！MoveNet 人体骨骼姿态识别系统已成功部署并运行！")
            print("[*] 请在手机浏览器中刷新: http://192.168.4.1:5000")
            print("[*] 站在免驱 USB 摄像头前，视频画面将实时画出 17 关节点动态骨架！")
            print("==================================================")
            return True
        else:
            print("[!] 服务未处于 active 状态，查看日志:")
            stdin, stdout, stderr = client.exec_command("journalctl -u pi-web.service -n 25 --no-pager")
            print(stdout.read().decode())
            return False

    except Exception as e:
        print(f"[!] 部署过程发生异常: {e}")
        return False
    finally:
        client.close()

if __name__ == "__main__":
    deploy()
