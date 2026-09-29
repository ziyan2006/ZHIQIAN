import socket, paramiko
sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
sock.settimeout(5.0)
sock.connect(('fe80::ba27:ebff:fea2:3b45', 22, 0, 10))
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('fe80::ba27:ebff:fea2:3b45', port=22, username='superboy', password='raspberry', sock=sock)

stdin, stdout, stderr = client.exec_command("python3 --version")
print("Python version:", stdout.read().decode())
client.close()
