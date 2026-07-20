#!/usr/bin/env python3
"""一键部署 Articles 服务到 jcloud

步骤:
1. scp articles_lib.py / app.py / articles.service 到 jcloud
2. 在 jcloud 写 /opt/articles/.env(包含密码 + API key)
3. systemctl enable + start articles.service
4. 注入 nginx location 段(注入到 /etc/nginx/sites-enabled/unified 末尾)
5. nginx -t && nginx -s reload
6. 验证 /articles/ 返回 200
"""
import os, sys, time
from pathlib import Path
from dotenv import load_dotenv
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

LOCAL_DIR = Path(r'D:\WorkSpace\Trading\Research\Articles')
load_dotenv(LOCAL_DIR / '.env')
REMOTE_DIR = '/opt/articles'

HOST = os.environ.get('JCLOUD_HOST', '111.228.51.56')
USER = os.environ.get('JCLOUD_USER', 'root')
PWD  = os.environ.get('JCLOUD_PWD', '')
# jcloud Flask /api/delete 的密码(从本地 .env 读,写入 jcloud /opt/articles/.env)
ARTICLES_PW = os.environ.get('ARTICLES_PASSWORD', '')

def ssh_exec(c, cmd, timeout=30):
    si, so, se = c.exec_command(cmd, timeout=timeout)
    out = so.read().decode('utf-8', errors='replace')
    err = se.read().decode('utf-8', errors='replace')
    code = so.channel.recv_exit_status()
    return code, out, err

def main():
    if not PWD or not ARTICLES_PW:
        print('ERROR: JCLOUD_PWD / ARTICLES_PASSWORD 未设置(请写入本地 .env)', file=sys.stderr)
        sys.exit(1)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD)
    print(f'✓ connected to {HOST}')

    sftp = c.open_sftp()

    # 1. 上传代码文件
    print(f'\n[1] 上传代码到 {REMOTE_DIR}/')
    sftp.mkdir(REMOTE_DIR)
    for f in ('articles_lib.py', 'app.py', 'articles.service', 'index.html'):
        local = LOCAL_DIR / f
        remote = f'{REMOTE_DIR}/{f}'
        sftp.put(str(local), remote)
        print(f'  ✓ {f}')

    # 2. 写 .env(在 jcloud 上,只放 ARTICLES_PASSWORD;翻译在本地跑,jcloud 不需要 ANTHROPIC_*)
    print(f'\n[2] 写 {REMOTE_DIR}/.env')
    env_content = f'ARTICLES_PASSWORD={ARTICLES_PW}\n'
    with sftp.file(f'{REMOTE_DIR}/.env', 'w') as f:
        f.write(env_content)
    sftp.chmod(f'{REMOTE_DIR}/.env', 0o600)
    print(f'  ✓ .env (ARTICLES_PASSWORD 已写入,值见本地 .env)')

    # 3. 创建 /var/www/articles 目录
    print(f'\n[3] mkdir /var/www/articles/')
    ssh_exec(c, 'mkdir -p /var/www/articles && chown -R www-data:www-data /var/www/articles /opt/articles')

    # 4. 部署 index.html 到 /var/www/articles/
    print(f'\n[4] 上传 UI 到 /var/www/articles/')
    sftp.put(str(LOCAL_DIR / 'index.html'), '/var/www/articles/index.html')
    print(f'  ✓ index.html')

    # 5. 部署 systemd service
    print(f'\n[5] systemctl 部署 articles.service')
    ssh_exec(c, f'cp {REMOTE_DIR}/articles.service /etc/systemd/system/articles.service')
    ssh_exec(c, 'systemctl daemon-reload')
    ssh_exec(c, 'systemctl enable articles.service')
    ssh_exec(c, 'systemctl restart articles.service')
    time.sleep(2)
    code, out, err = ssh_exec(c, 'systemctl is-active articles')
    print(f'  status: {out.strip()}')
    if 'active' not in out:
        print(f'  ❌ service not active. err: {err}')
        code, out, err = ssh_exec(c, 'journalctl -u articles -n 30 --no-pager')
        print(out)
        sys.exit(1)

    # 6. 注入 nginx 段
    print(f'\n[6] 注入 nginx location 段')
    snippet = (LOCAL_DIR / 'nginx_snippet.conf').read_text(encoding='utf-8')

    # 用 sed 在 server { ... } 块的最后一行前插入(在最后一个 } 之前)
    # 简单做法:在文件末尾 "}\n" 之前插入
    nginx_conf = '/etc/nginx/sites-enabled/unified'
    code, conf, _ = ssh_exec(c, f'cat {nginx_conf}')
    if '/articles/' in conf:
        print(f'  ⚠️ /articles/ 已存在,跳过注入')
    else:
        # 找到最后一个 } 的位置(文件末尾)
        last_brace = conf.rstrip().rfind('}')
        if last_brace == -1:
            print(f'  ❌ 找不到 }} 位置')
            sys.exit(1)
        new_conf = conf[:last_brace] + '\n' + snippet + conf[last_brace:]
        with sftp.file(nginx_conf, 'w') as f:
            f.write(new_conf)
        print(f'  ✓ 注入完成')

    # 7. nginx -t && reload
    print(f'\n[7] nginx 测试 + 重载')
    code, out, err = ssh_exec(c, 'nginx -t 2>&1')
    print(out)
    if code != 0:
        print(f'  ❌ nginx -t 失败')
        sys.exit(1)
    ssh_exec(c, 'nginx -s reload')
    print(f'  ✓ nginx reloaded')

    # 8. 验证
    print(f'\n[8] 端到端验证')
    time.sleep(2)
    code, out, err = ssh_exec(c, 'curl -s -o /dev/null -w "GET /articles/         : %{http_code}\\n" https://buumicloud.com.cn/articles/')
    print(out.strip())
    code, out, err = ssh_exec(c, 'curl -s -o /dev/null -w "GET /articles/api/list : %{http_code}\\n" https://buumicloud.com.cn/articles/api/list')
    print(out.strip())
    code, out, err = ssh_exec(c, 'curl -s https://buumicloud.com.cn/articles/api/health')
    print(f'  health: {out.strip()}')

    sftp.close()
    c.close()
    print(f'\n✅ 部署完成!')
    print(f'   UI:  https://buumicloud.com.cn/articles/')
    print(f'   密码: 见本地 .env ARTICLES_PASSWORD')

if __name__ == '__main__':
    main()
