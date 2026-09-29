import socket
import paramiko
import os

print("[*] Connecting via IPv6 socket...")
sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.settimeout(5.0)
sock.connect(('fe80::ba27:ebff:fea2:3b45', 22, 0, 10))

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('fe80::ba27:ebff:fea2:3b45', port=22, username='superboy', password='raspberry', sock=sock)
print("[+] SSH Connected!")

# Upload updated pose_detector.py and app.py
sftp = client.open_sftp()
base_dir = r"d:\Codex\智嵌\pi_web_server"
for f in ["pose_detector.py", "app.py", os.path.join("templates", "index.html"), os.path.join("static", "js", "dashboard.js")]:
    local_path = os.path.join(base_dir, f)
    remote_path = "/home/superboy/pi_web_server/" + f.replace("\\", "/")
    print(f"[*] Uploading {f} -> {remote_path} ...")
    sftp.put(local_path, remote_path)
sftp.close()
print("[+] Files uploaded!")

# Extract tflite_runtime from the whl on Pi
cmd = """
python3 -m zipfile -e /home/superboy/pi_web_server/models/tflite_runtime-2.16.1-cp311-none-linux_aarch64.whl /home/superboy/pi_web_server/
echo raspberry | sudo -S systemctl restart pi-web.service
sleep 1.5
systemctl is-active pi-web.service
"""
stdin, stdout, stderr = client.exec_command(cmd)
print("[+] Result:\n" + stdout.read().decode('utf-8', errors='replace'))
print("[+] Errors:\n" + stderr.read().decode('utf-8', errors='replace'))

# Test MoveNet on Pi
test_cmd = """python3 - << 'EOF'
import sys
sys.path.insert(0, '/home/superboy/pi_web_server')
from pose_detector import MoveNetPoseDetector
import numpy as np

detector = MoveNetPoseDetector('/home/superboy/pi_web_server/models/movenet_lightning_int8.tflite')
print('Pose Detector is_ready:', detector.is_ready())
if detector.is_ready():
    dummy = np.zeros((360, 640, 3), dtype=np.uint8)
    frame, stats = detector.detect_and_draw(dummy)
    print('MoveNet test inference on Pi:', stats)
EOF
"""
stdin, stdout, stderr = client.exec_command(test_cmd)
print("[+] Inference Test:\n" + stdout.read().decode('utf-8', errors='replace'))
print("[+] Inference Err:\n" + stderr.read().decode('utf-8', errors='replace'))

client.close()
print("[*] Done!")
