import socket
import paramiko
import time

sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.connect(('fe80::ba27:ebff:fea2:3b45', 22, 0, 10))
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('fe80::ba27:ebff:fea2:3b45', port=22, username='superboy', password='raspberry', sock=sock)

remote_script = """
import urllib.request
import time

req = urllib.request.urlopen("http://127.0.0.1:5000/api/camera/stream", timeout=15)
buf = b""
start = time.time()
last_frame = None

# Stream for 5 seconds to let YOLOv8-pose run background inference cycles
while time.time() - start < 5.0:
    chunk = req.read(4096)
    buf += chunk
    a = buf.find(b"\\xff\\xd8")
    b = buf.find(b"\\xff\\xd9")
    if a != -1 and b != -1 and b > a:
        last_frame = buf[a:b+2]
        buf = buf[b+2:]

if last_frame:
    with open("/tmp/pi_camera_snap_active.jpg", "wb") as f:
        f.write(last_frame)
    print("SAVED_ACTIVE_FRAME")
"""

stdin, stdout, stderr = ssh.exec_command("python3 -c '" + remote_script.replace("'", "\\'") + "'")
print("CAPTURE STDOUT:", stdout.read().decode('utf-8', errors='ignore'))
print("CAPTURE STDERR:", stderr.read().decode('utf-8', errors='ignore'))

try:
    sftp = ssh.open_sftp()
    sftp.get("/tmp/pi_camera_snap_active.jpg", "C:/Users/30519/.gemini/antigravity/brain/71056fa9-6edb-4deb-bf36-a939ec90c505/pi_live_snap_active.jpg")
    sftp.close()
    print("Frame downloaded!")
except Exception as e:
    print("Download error:", e)

stdin, stdout, stderr = ssh.exec_command("curl -s http://127.0.0.1:5000/api/status")
print("Status after stream:", stdout.read().decode('utf-8', errors='ignore'))

ssh.close()
