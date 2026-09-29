import socket, paramiko
sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.settimeout(5.0)
sock.connect(('fe80::ba27:ebff:fea2:3b45', 22, 0, 10))
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('fe80::ba27:ebff:fea2:3b45', port=22, username='superboy', password='raspberry', sock=sock)

test_py = """python3 - << 'EOF'
import cv2
print('OpenCV version:', cv2.__version__)
print('Testing cv2.dnn...')

# Test reading movenet onnx
try:
    net = cv2.dnn.readNetFromONNX('/home/superboy/pi_web_server/models/movenet_singlepose_lightning_4.onnx')
    print('ONNX SUCCESS on Pi OpenCV 4.10!')
except Exception as e:
    print('ONNX Error on Pi:', e)

# Test reading movenet tflite
try:
    net_tf = cv2.dnn.readNet('/home/superboy/pi_web_server/models/movenet_lightning_int8.tflite')
    print('TFLite SUCCESS on Pi OpenCV 4.10!')
except Exception as e:
    print('TFLite Error on Pi:', e)
EOF
"""

# Upload movenet_singlepose_lightning_4.onnx if not exists
sftp = client.open_sftp()
local_onnx = r"d:\Codex\智嵌\movenet_singlepose_lightning_4.onnx"
remote_onnx = "/home/superboy/pi_web_server/models/movenet_singlepose_lightning_4.onnx"
import os
if os.path.exists(local_onnx):
    print("Uploading ONNX model to Pi...")
    sftp.put(local_onnx, remote_onnx)
    print("ONNX uploaded!")
sftp.close()

stdin, stdout, stderr = client.exec_command(test_py)
print("STDOUT:\n" + stdout.read().decode())
print("STDERR:\n" + stderr.read().decode())
client.close()
