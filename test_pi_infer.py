import sync_final

ssh = sync_final.connect_pi()
if not ssh:
    print("Could not connect to Pi!")
    exit(1)

cmd = """python3 - << 'EOF'
import cv2
import time
import numpy as np

print("OpenCV version:", cv2.__version__)
print("Default threads:", cv2.getNumThreads())

model_path = '/home/superboy/pi_web_server/models/yolov8n-pose.onnx'
net = cv2.dnn.readNetFromONNX(model_path)
print("Model loaded successfully!")
dummy = np.zeros((360, 640, 3), dtype=np.uint8)
blob = cv2.dnn.blobFromImage(dummy, 1/255.0, (640, 640), swapRB=True, crop=False)

for n_threads in [1, 2, 3, 4]:
    cv2.setNumThreads(n_threads)
    net.setInput(blob)
    t0 = time.time()
    out = net.forward()
    dt = (time.time() - t0) * 1000
    print(f"Threads={n_threads}: forward={dt:.1f}ms")
EOF
"""
stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:\n", stdout.read().decode())
print("STDERR:\n", stderr.read().decode())
ssh.close()
