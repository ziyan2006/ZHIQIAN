import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

for host in ['fe80::ba27:ebff:fea2:3b45', 'superboy-2.local', '192.168.4.1']:
    try:
        client.connect(host, port=22, username='superboy', password='raspberry', timeout=4)
        print("Connected via:", host)
        break
    except Exception as e:
        print(f"{host} failed: {e}")

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode('utf-8', errors='replace').strip()

print("Python Version:", run("python3 -c 'import sys; print(sys.version)'"))
print("Architecture:", run("uname -m; dpkg --print-architecture"))
print("Pip tags:", run("python3 -c 'from pip._internal.utils.compatibility_tags import get_supported; print([str(t) for t in get_supported()[:8]])'"))
print("Apt search tflite:", run("apt-cache search tflite 2>/dev/null"))

client.close()
