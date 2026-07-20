import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('111.228.51.56', 22, 'root', 'pUUkenQ^')

# Check current state
cmd = 'ps aux | grep node | grep -v grep'
stdin, stdout, stderr = client.exec_command(cmd)
print('Node before restart:', stdout.read().decode())

# Kill and restart
commands = [
    'pkill -f "node src/server" || true',
    'sleep 1',
    'cd /var/www/bulb-system && NODE_ENV=production nohup node src/server/index.js >> /var/log/bulb-server.log 2>&1 &',
    'sleep 3',
    'ps aux | grep node | grep -v grep'
]

for cmd in commands:
    stdin, stdout, stderr = client.exec_command(cmd)
    print(f'CMD: {cmd}')
    print('  stdout:', stdout.read().decode())

client.close()