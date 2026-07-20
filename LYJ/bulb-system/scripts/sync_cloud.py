import paramiko, os, time

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('111.228.51.56', 22, 'root', 'pUUkenQ^')

sftp = client.open_sftp()

# Upload server files
files = [
    'src/server/index.js',
    'src/server/db/init.js',
    'src/server/routes/projectors.js',
    'src/server/routes/skus.js',
    'src/server/routes/replacements.js',
    'src/server/routes/users.js',
    'src/server/routes/import.js',
    'src/client/src/pages/admin/ProjectorManagement.jsx',
    'src/client/src/pages/admin/SKUManagement.jsx',
    'src/client/src/pages/admin/Dashboard.jsx',
    'src/client/src/pages/facility/ReplacementForm.jsx',
    'src/client/src/pages/facility/ProjectorDetail.jsx',
    'src/client/src/pages/facility/Dashboard.jsx',
    'src/client/src/pages/asset/Dashboard.jsx',
    'src/client/src/pages/asset/InventoryOverview.jsx',
    'src/client/src/pages/supplier/Dashboard.jsx',
    'src/client/src/pages/supplier/ShipmentForm.jsx',
    'src/client/src/components/DashboardLayout.jsx',
]

for f in files:
    local_path = os.path.join('D:/workspace/worktools/bulb-system', f)
    remote_path = f'/var/www/bulb-system/{f}'
    sftp.put(local_path, remote_path)
    print(f'Uploaded: {f}')

sftp.close()

# Upload frontend dist
local_dist = 'D:/workspace/worktools/bulb-system/src/dist'
remote_dist = '/var/www/bulb-system/src/dist'

stdin, stdout, stderr = client.exec_command(f'rm -rf {remote_dist} && mkdir -p {remote_dist}')
stdout.read()
stderr.read()

sftp = client.open_sftp()
for root, dirs, files in os.walk(local_dist):
    for file in files:
        local_path = os.path.join(root, file)
        rel_path = os.path.relpath(local_path, local_dist).replace('\\', '/')
        remote_path = f'{remote_dist}/{rel_path}'
        remote_dir = os.path.dirname(remote_path).replace('\\', '/')
        try:
            sftp.stat(remote_dir)
        except:
            sftp.mkdir(remote_dir)
        sftp.put(local_path, remote_path)
sftp.close()

# Restart node
stdin, stdout, stderr = client.exec_command('cd /var/www/bulb-system && pkill -f "node src/server" 2>/dev/null; sleep 1; setsid env TZ=Asia/Shanghai NODE_ENV=production node src/server/index.js </dev/null >/var/log/bulb-server.log 2>&1 &')
time.sleep(3)

stdin, stdout, stderr = client.exec_command('curl -s http://localhost:3001/api/health')
print('Health:', stdout.read().decode())

client.close()
print('Done!')