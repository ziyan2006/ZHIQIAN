import socket, paramiko, os, time

sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.settimeout(5.0)
sock.connect(('fe80::ba27:ebff:fea2:3b45', 22, 0, 10))
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('fe80::ba27:ebff:fea2:3b45', port=22, username='superboy', password='raspberry', sock=sock)

local_p = r"d:\Codex\智嵌\yolov8n-pose.onnx"
remote_p = "/home/superboy/pi_web_server/models/yolov8n-pose.onnx"

sftp = client.open_sftp()
print(f"Uploading {os.path.basename(local_p)} ({os.path.getsize(local_p)/(1024*1024):.1f} MB)...")
sftp.put(local_p, remote_p)
print("Uploaded successfully!")
sftp.close()

# Test on Pi
test_py = """python3 - << 'EOF'
import cv2, numpy as np, time
print('Loading yolov8n-pose in OpenCV DNN on Pi...')
t0 = time.time()
net = cv2.dnn.readNetFromONNX('/home/superboy/pi_web_server/models/yolov8n-pose.onnx')
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
print(f'Model loaded in {(time.time() - t0):.2f}s!')

dummy = np.zeros((640, 640, 3), dtype=np.uint8)
blob = cv2.dnn.blobFromImage(dummy, 1/255.0, (640, 640), swapRB=True, crop=False)
net.setInput(blob)

t1 = time.time()
out = net.forward()
infer_ms = (time.time() - t1) * 1000
print(f'Pi CPU Inference: {infer_ms:.1f}ms, Output shape: {out.shape}')
EOF
"""
stdin, stdout, stderr = client.exec_command(test_py)
print("STDOUT:\n" + stdout.read().decode())
print("STDERR:\n" + stderr.read().decode())
client.close()
