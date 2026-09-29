import sys
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('superboy-2.local', port=22, username='superboy', password='raspberry', timeout=5)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

out, err = run("python3 -c 'import tflite_runtime; print(\"TFLITE_OK:\", tflite_runtime.__file__)'")
print("TFLite check:", out, err)

if "TFLITE_OK" not in out:
    print("Installing wheel...")
    out_inst, err_inst = run("python3 -m pip install /home/superboy/pi_web_server/models/tflite_runtime-2.16.1-cp311-none-linux_aarch64.whl --no-index --find-links /home/superboy/pi_web_server/models --break-system-packages")
    print("Pip install:", out_inst, err_inst)
    
    out, err = run("python3 -c 'import tflite_runtime; print(\"TFLITE_OK:\", tflite_runtime.__file__)'")
    print("TFLite check 2:", out, err)
    
    print("Restarting service...")
    out_rst, _ = run("echo raspberry | sudo -S systemctl restart pi-web.service")
    print("Restart:", out_rst)

print("\n--- Testing MoveNet pose detection directly on Pi ---")
test_script = """python3 - << 'EOF'
import sys
sys.path.insert(0, '/home/superboy/pi_web_server')
from pose_detector import MoveNetPoseDetector
import numpy as np

detector = MoveNetPoseDetector('/home/superboy/pi_web_server/models/movenet_lightning_int8.tflite')
print('Detector ready:', detector.is_ready())
if detector.is_ready():
    dummy = np.zeros((360, 640, 3), dtype=np.uint8)
    frame, stats = detector.detect_and_draw(dummy)
    print('MoveNet inference test stats:', stats)
EOF
"""
out_t, err_t = run(test_script)
print("Pose Detector Test:\n", out_t)
if err_t:
    print("Pose Detector Errors:\n", err_t)

print("\n--- Systemd Service Journal (Latest) ---")
out_j, _ = run("journalctl -u pi-web.service -n 12 --no-pager")
print(out_j)

client.close()
