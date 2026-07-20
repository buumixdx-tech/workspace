#!/usr/bin/env python3
"""重部署简化的 Articles 到 jcloud(只推 app.py 和 index.html)"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import paramiko
from pathlib import Path
from dotenv import load_dotenv

LOCAL = Path(r'D:\WorkSpace\Trading\Research\Articles')
load_dotenv(LOCAL / '.env')
HOST = os.environ.get('JCLOUD_HOST', '111.228.51.56')
USER = os.environ.get('JCLOUD_USER', 'root')
PWD  = os.environ.get('JCLOUD_PWD', '')

if not PWD:
    print('ERROR: JCLOUD_PWD 未设置(请写入本地 .env)', file=sys.stderr)
    sys.exit(1)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD)
sftp = c.open_sftp()

print('[1] 上传 app.py → /opt/articles/app.py')
sftp.put(str(LOCAL / 'app.py'), '/opt/articles/app.py')

print('[2] 上传 index.html → /var/www/articles/index.html')
sftp.put(str(LOCAL / 'index.html'), '/var/www/articles/index.html')

# 同样需要 articles_lib 在 jcloud 上(因为 app.py import 了 list_articles)
print('[3] 确保 articles_lib.py 在 jcloud')
try:
    sftp.stat('/opt/articles/articles_lib.py')
    print('  ✓ 已存在')
except IOError:
    print('  上传...')
    sftp.put(str(LOCAL / 'articles_lib.py'), '/opt/articles/articles_lib.py')

# app.py 仍读 ARTICLES_PASSWORD(来自 /opt/articles/.env),这里不碰它;首次部署由 deploy_to_jcloud.py 写入
print('[4] 重启 articles.service')
si, so, se = c.exec_command('systemctl restart articles.service && sleep 2 && systemctl is-active articles')
print(f'  status: {so.read().decode().strip()}')

import time
time.sleep(2)

# 验证
print('\n[5] 验证 API')
si, so, se = c.exec_command('curl -s https://buumicloud.com.cn/articles/api/health')
print(f'  health: {so.read().decode().strip()}')
si, so, se = c.exec_command('curl -s -o /dev/null -w "GET /articles/         : %{http_code}\\nGET /articles/api/list : " https://buumicloud.com.cn/articles/ && curl -s -o /dev/null -w "%{http_code}\\n" https://buumicloud.com.cn/articles/api/list')
print(f'  {so.read().decode().strip()}')

sftp.close()
c.close()
