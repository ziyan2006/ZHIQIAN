import paramiko

def run_ssh(cmd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect('fe80::ba27:ebff:fea2:3b45', port=22, username='superboy', password='raspberry', timeout=5)
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    client.close()
    return out, err

out, err = run_ssh("python3 -c 'import cv2; print(\"CV:\", cv2.__version__, \"DNN:\", hasattr(cv2, \"dnn\"))'")
print("OUT:", out)
print("ERR:", err)
