"""sync_all_to_jcloud.py — 把本地所有 article_<sid>.html + assets/<sid>/ 上传到 jcloud.

跟 build_article.py 的 upload 段一样,但批量 + 复用同一个 SSH 连接。
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv
import paramiko

LOCAL_DIR = Path(r'D:\WorkSpace\Trading\Research\Articles')
load_dotenv(LOCAL_DIR / '.env')
JCLOUD_HOST = os.environ.get('JCLOUD_HOST', '111.228.51.56')
JCLOUD_USER = os.environ.get('JCLOUD_USER', 'root')
JCLOUD_PWD = os.environ.get('JCLOUD_PWD', '')   # 从本地 .env 读
JCLOUD_ARTICLES_DIR = '/var/www/articles'


def main() -> int:
    html_files = sorted(LOCAL_DIR.glob('article_*.html'))
    if not html_files:
        print('no local articles found')
        return 1

    print(f'found {len(html_files)} articles locally')
    for h in html_files:
        sid = h.stem.removeprefix('article_')
        ad = LOCAL_DIR / 'assets' / sid
        n_imgs = len(list(ad.iterdir())) if ad.exists() else 0
        print(f'  - {sid}  {h.stat().st_size:>7,}B  assets={n_imgs}')

    if not JCLOUD_PWD:
        print('ERROR: JCLOUD_PWD 未设置(请写入本地 .env)', file=sys.stderr)
        return 1
    print(f'\n[connect] {JCLOUD_USER}@{JCLOUD_HOST}')
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(JCLOUD_HOST, username=JCLOUD_USER, password=JCLOUD_PWD)
    sftp = c.open_sftp()

    for h in html_files:
        sid = h.stem.removeprefix('article_')
        remote_html = f'{JCLOUD_ARTICLES_DIR}/{h.name}'
        print(f'\n[upload] {sid}')
        print(f'  [1/3] {h.name} ({h.stat().st_size:,}B)')
        sftp.put(str(h), remote_html)
        sftp.chmod(remote_html, 0o664)

        ad = LOCAL_DIR / 'assets' / sid
        if ad.exists():
            imgs = list(ad.iterdir())
            remote_assets = f'{JCLOUD_ARTICLES_DIR}/assets/{sid}'
            try:
                sftp.mkdir(remote_assets)
            except IOError:
                pass
            print(f'  [2/3] assets/{sid}/ ({len(imgs)} files)')
            for f in imgs:
                rp = f'{remote_assets}/{f.name}'
                sftp.put(str(f), rp)
                sftp.chmod(rp, 0o664)
        else:
            print(f'  [2/3] no assets dir, skip')

    # chown 一次性给所有 path
    print('\n[chown] www-data:www-data')
    chown_paths = ' '.join(
        f'{JCLOUD_ARTICLES_DIR}/{h.name}' for h in html_files
    )
    stdin, stdout, stderr = c.exec_command(f'chown -R www-data:www-data {chown_paths}')
    err = stderr.read().decode().strip()
    if err:
        print(f'  WARN: {err}')
    else:
        print(f'  OK ({len(html_files)} html paths)')

    sftp.close()
    c.close()
    # GBK console 没法输出 emoji, 用 ASCII
    print('\n[OK] all uploaded')
    print('public URLs:')
    for h in html_files:
        sid = h.stem.removeprefix('article_')
        print(f'  https://buumicloud.com.cn/articles/article_{sid}.html')
    return 0


if __name__ == '__main__':
    sys.exit(main())