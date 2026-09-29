import sync_final

ssh = sync_final.connect_pi()
if not ssh:
    print("Failed to connect")
    exit(1)

cmd = """python3 - << 'EOF'
import cv2
import os
import subprocess

print("lsusb:")
print(subprocess.getoutput("lsusb"))

print("ls -l /dev/video*:")
print(subprocess.getoutput("ls -l /dev/video*"))

for idx in [0, 1, 2, 10]:
    cap = cv2.VideoCapture(idx)
    opened = cap.isOpened()
    print(f"VideoCapture({idx}) isOpened: {opened}")
    if opened:
        ret, frame = cap.read()
        print(f"  cap.read() ret={ret}, shape={frame.shape if frame is not None else None}")
        cap.release()
EOF
"""
stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))

# Check app.py process and logs
stdin, stdout, stderr = ssh.exec_command("journalctl -u pi-web.service -n 20 --no-pager")
print("Logs:\n", stdout.read().decode('utf-8', errors='ignore'))

ssh.close()
