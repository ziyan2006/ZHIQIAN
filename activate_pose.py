import socket
import paramiko

sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.settimeout(5.0)
sock.connect(('fe80::ba27:ebff:fea2:3b45', 22, 0, 10))
print('[1] Raw IPv6 socket connected successfully!')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('fe80::ba27:ebff:fea2:3b45', port=22, username='superboy', password='raspberry', sock=sock)
print('[2] Paramiko SSH session established!')

# Extract tflite_runtime wheel directly on Pi!
cmd = """
python3 -m zipfile -e /home/superboy/pi_web_server/models/tflite_runtime-2.16.1-cp311-none-linux_aarch64.whl /home/superboy/pi_web_server/
python3 -c "import sys; sys.path.insert(0, '/home/superboy/pi_web_server'); import tflite_runtime; print('TFLITE_OK:', tflite_runtime.__file__)"
"""
stdin, stdout, stderr = client.exec_command(cmd)
print('[3] Extract & test:\n' + stdout.read().decode('utf-8', errors='replace'))
err = stderr.read().decode('utf-8', errors='replace')
if err:
    print('Errors:\n' + err)

# Test MoveNet pose detector directly
cmd_test = """
python3 - << 'EOF'
import sys
sys.path.insert(0, '/home/superboy/pi_web_server')
from pose_detector import MoveNetPoseDetector
import numpy as np

detector = MoveNetPoseDetector('/home/superboy/pi_web_server/models/movenet_lightning_int8.tflite')
print('Detector ready:', detector.is_ready())
if detector.is_ready():
    dummy = np.zeros((360, 640, 3), dtype=np.uint8)
    frame, stats = detector.detect_and_draw(dummy)
    print('MoveNet inference test stats on Pi CPU:', stats)
EOF
"""
stdin, stdout, stderr = client.exec_command(cmd_test)
print('[4] Pose detector test:\n' + stdout.read().decode('utf-8', errors='replace'))
err_test = stderr.read().decode('utf-8', errors='replace')
if err_test:
    print('Pose detector err:\n' + err_test)

# Restart service
cmd_restart = 'echo raspberry | sudo -S systemctl restart pi-web.service'
stdin, stdout, stderr = client.exec_command(cmd_restart)
stdout.channel.recv_exit_status()
print('[5] Service restarted!')

stdin, stdout, stderr = client.exec_command('systemctl is-active pi-web.service')
print('[6] Service state:', stdout.read().decode().strip())

client.close()
