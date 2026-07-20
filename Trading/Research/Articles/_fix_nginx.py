import os, paramiko
from dotenv import load_dotenv
load_dotenv(r'D:\WorkSpace\Trading\Research\Articles\.env')
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(os.environ['JCLOUD_HOST'], username=os.environ['JCLOUD_USER'], password=os.environ['JCLOUD_PWD'])

def run(cmd):
    si, so, se = c.exec_command(cmd)
    out = so.read().decode(errors='replace')
    err = se.read().decode(errors='replace')
    code = so.channel.recv_exit_status()
    print(f'$ {cmd}')
    if out: print(out.rstrip())
    if err: print('  [stderr]', err.rstrip())
    print(f'  [exit {code}]')
    return code, out, err

BAK = '/etc/nginx/sites-enabled/unified.bak.articles.20260717'
CONF = '/etc/nginx/sites-enabled/unified'

# 1. 备份
run(f'cp {CONF} {BAK}')

# 2. 读 + 替换
sftp = c.open_sftp()
content = sftp.file(CONF, 'r').read().decode('utf-8')

old = """    # ===== articles (2026-07-08) =====
    location /articles/ {
        rewrite ^/articles/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:5000;
        include snippets/proxy_headers.conf;
        client_max_body_size 50M;
    }
    location /articles {
        return 301 /articles/;
    }"""

new = """    # ===== articles (2026-07-17) ===== 静态由 nginx 直接 serve,仅 /articles/api/ 转发 Flask
    location /articles/ {
        root /var/www;
        index index.html;
        autoindex off;
        try_files $uri $uri/ =404;
    }
    location /articles/api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        include snippets/proxy_headers.conf;
        proxy_read_timeout 180s;
        client_max_body_size 50M;
    }
    location /articles {
        return 301 /articles/;
    }"""

if old not in content:
    print('ERROR: old block not found exactly, aborting (不写回)')
    sftp.close(); c.close(); raise SystemExit(1)

content2 = content.replace(old, new, 1)
sftp.file(CONF, 'w').write(content2)
print('config written (替换 1 处)\n')

# 3. nginx -t
code, _, _ = run('nginx -t 2>&1')
if code != 0:
    print('!!! nginx -t FAILED, restoring backup')
    run(f'cp {BAK} {CONF}')
    run('nginx -t 2>&1')
    sftp.close(); c.close(); raise SystemExit(1)

# 4. reload
run('nginx -s reload')
print()

# 5. jcloud 本地验证(带 Host 走 buumicloud server 块)
H = '-H "Host: buumicloud.com.cn" http://localhost'
run(f'curl -s -o /dev/null -w "  /articles/             : %{{http_code}}\\n" {H}/articles/')
run(f'curl -s -o /dev/null -w "  /articles/article html : %{{http_code}}\\n" {H}/articles/article_2077699981990133958.html')
run(f'curl -s -o /dev/null -w "  /articles/assets/img1  : %{{http_code}}\\n" {H}/articles/assets/2077699981990133958/img_01.jpg')
run(f'curl -s -o /dev/null -w "  /articles/api/health   : %{{http_code}}\\n" {H}/articles/api/health')

sftp.close(); c.close()
