import paramiko, os

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('111.228.51.56', 22, 'root', 'pUUkenQ^')

sftp = client.open_sftp()
sftp.put('D:/workspace/worktools/bulb-system/check_cloud.js', '/var/www/bulb-system/check_cloud.js')
sftp.close()

stdin, stdout, stderr = client.exec_command('cd /var/www/bulb-system && node check_cloud.js')
print('stdout:', stdout.read().decode())
print('stderr:', stderr.read().decode())

client.close()