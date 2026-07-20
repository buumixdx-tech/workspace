import paramiko
import sys

host = "111.228.51.56"
username = "root"
password = "pUUkenQ^"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(hostname=host, username=username, password=password, timeout=10)
    print("Connected successfully!")

    # Run a simple command
    stdin, stdout, stderr = client.exec_command("echo 'Hello from server' && uname -a")
    print(stdout.read().decode())
    if stderr.read().decode():
        print("Stderr:", stderr.read().decode())

    client.close()
    print("Connection closed.")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
