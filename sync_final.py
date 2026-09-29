import socket
import paramiko
import os
import time
import subprocess

BASE_DIR = r"d:\Codex\智嵌\pi_web_server"

def connect_pi():
    # 预先向目标单播 IPv6 发送 ICMP 探测，强制内核将邻居表置为 Reachable
    subprocess.run(["ping", "-6", "-n", "2", "fe80::ba27:ebff:fea2:3b45%10"], capture_output=True)
    for attempt in range(1, 15):
        try:
            sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect(('fe80::ba27:ebff:fea2:3b45', 22, 0, 10))
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect('fe80::ba27:ebff:fea2:3b45', port=22, username='superboy', password='raspberry', sock=sock)
            print(f"[+] 成功连接树莓派 (第 {attempt} 次尝试)")
            return client
        except Exception as e:
            pass

        # 唤醒直连探测
        subprocess.run(["ping", "-6", "-n", "1", "fe80::ba27:ebff:fea2:3b45%10"], capture_output=True)
        time.sleep(1.0)

    return None

def main():
    print("[*] 正在同步最终 AI 骨骼姿态识别系统至树莓派...")
    client = connect_pi()
    if not client:
        print("[!] 连接失败，请检查网线。")
        return

    sftp = client.open_sftp()
    
    # 1. 上传 pose_detector.py, app.py, index.html, dashboard.js
    files_to_sync = [
        ("pose_detector.py", "/home/superboy/pi_web_server/pose_detector.py"),
        ("app.py", "/home/superboy/pi_web_server/app.py"),
        (os.path.join("templates", "index.html"), "/home/superboy/pi_web_server/templates/index.html"),
        (os.path.join("static", "js", "dashboard.js"), "/home/superboy/pi_web_server/static/js/dashboard.js"),
    ]
    for local_rel, remote_p in files_to_sync:
        local_p = os.path.join(BASE_DIR, local_rel)
        print(f"[*] 上传 {local_rel} ...")
        sftp.put(local_p, remote_p)
    
    # 2. 上传 yolov8n-pose-256.onnx (高速模型)
    local_yolo256 = os.path.join(BASE_DIR, "models", "yolov8n-pose-256.onnx")
    remote_yolo256 = "/home/superboy/pi_web_server/models/yolov8n-pose-256.onnx"
    try:
        remote_stat = sftp.stat(remote_yolo256)
        if remote_stat.st_size == os.path.getsize(local_yolo256):
            print(f"[+] 远程已存在完整 yolov8n-pose-256.onnx ({remote_stat.st_size/(1024*1024):.1f} MB)")
        else:
            raise FileNotFoundError()
    except Exception:
        print(f"[*] 上传 yolov8n-pose-256.onnx ({os.path.getsize(local_yolo256)/(1024*1024):.1f} MB)...")
        sftp.put(local_yolo256, remote_yolo256)
        print("[+] yolov8n-pose-256.onnx 上传完毕！")
    
    sftp.close()

    # 3. 重启服务
    print("[*] 重启 pi-web.service ...")
    stdin, stdout, stderr = client.exec_command("echo raspberry | sudo -S systemctl restart pi-web.service")
    stdout.channel.recv_exit_status()
    time.sleep(1.5)

    # 4. 在树莓派上测试 PoseDetector 状态
    test_cmd = """python3 - << 'EOF'
import sys
sys.path.insert(0, '/home/superboy/pi_web_server')
from pose_detector import MoveNetPoseDetector
import numpy as np

detector = MoveNetPoseDetector()
print('Pose Detector is_ready on Pi:', detector.is_ready())
print('Active Model imgsz:', detector.imgsz, 'Mode:', detector.mode)
if detector.is_ready():
    dummy = np.zeros((360, 640, 3), dtype=np.uint8)
    frame, stats = detector.detect_and_draw(dummy)
    print('Pi CPU OpenCV DNN Test:', stats)
EOF
"""
    stdin, stdout, stderr = client.exec_command(test_cmd)
    print("[+] 测试输出:\n" + stdout.read().decode())
    print("[+] 错误输出:\n" + stderr.read().decode())

    # 5. 校验服务状态
    stdin, stdout, stderr = client.exec_command("systemctl is-active pi-web.service")
    state = stdout.read().decode().strip()
    print(f"[+] 服务状态: {state}")

    client.close()
    if state == "active":
        print("[SUCCESS] 骨骼识别服务已成功上线！")

if __name__ == "__main__":
    main()
