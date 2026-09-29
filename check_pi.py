import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('fe80::ba27:ebff:fea2:3b45%10', port=22, username='superboy', password='raspberry', timeout=5)

script = """
python3 - << 'EOF'
import cv2
print("CV2 Version:", cv2.__version__)
print("Has cv2.dnn:", hasattr(cv2, 'dnn'))

for mod in ['mediapipe', 'tflite_runtime', 'onnxruntime', 'torch']:
    try:
        __import__(mod)
        print(f"{mod}: Available")
    except ImportError:
        print(f"{mod}: Not installed")

EOF
"""

stdin, stdout, stderr = client.exec_command(script)
print("STDOUT:\n" + stdout.read().decode('utf-8', errors='replace'))
print("STDERR:\n" + stderr.read().decode('utf-8', errors='replace'))
client.close()
