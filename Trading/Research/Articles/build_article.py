#!/usr/bin/env python3
"""CLI 包装: 调用 articles_lib.build_article() + 可选 scp 到 jcloud

用法:
    python build_article.py                              # 默认 URL + 不翻译
    python build_article.py -u <X_URL>                   # 自定义 URL + 不翻译
    python build_article.py -u <X_URL> --translate       # 翻译后再渲染
    python build_article.py -u <X_URL> --upload-jcloud   # 完成后 scp 到 jcloud
    python build_article.py -u <X_URL> --upload-jcloud --translate
"""
import sys, os, argparse
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')
from articles_lib import build_article

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DEFAULT_URL = 'https://x.com/JoeAnima/status/2071782733718958348'
OUT_DIR = Path(r'D:\WorkSpace\Trading\Research\Articles')

# jcloud 部署目标
JCLOUD_HOST = os.environ.get('JCLOUD_HOST', '111.228.51.56')
JCLOUD_USER = os.environ.get('JCLOUD_USER', 'root')
JCLOUD_PWD  = os.environ.get('JCLOUD_PWD', '')   # 从本地 .env 读,不写死
JCLOUD_ARTICLES_DIR = '/var/www/articles'

ap = argparse.ArgumentParser()
ap.add_argument('-u', '--url', default=DEFAULT_URL)
ap.add_argument('--translate', action='store_true', help='翻译后再渲染(默认不翻译)')
ap.add_argument('--no-docx', action='store_true', help='跳过 docx(目前未实现,忽略)')
ap.add_argument('--docx', default=None, help='docx 路径(目前未实现,忽略)')
ap.add_argument('--out-dir', default=str(OUT_DIR))
ap.add_argument('--out', default=None, help='输出 HTML 路径(默认按 sid 命名)')
ap.add_argument('--upload-jcloud', action='store_true', help='完成后 scp 到 jcloud')
args = ap.parse_args()

print(f'[1] URL: {args.url}')
print(f'[2] translate: {args.translate}')
print(f'[3] output_dir: {args.out_dir}')
print(f'[4] upload to jcloud: {args.upload_jcloud}')

result = build_article(
    url=args.url,
    translate=args.translate,
    output_dir=Path(args.out_dir),
    docx_path=args.docx,
)
sid = result['sid']
out_file = result['path']
assets_dir = Path(args.out_dir) / 'assets' / sid

print(f'\n✅ {out_file} ({out_file.stat().st_size:,} bytes)')
print(f'   title: {result["title"]}')
print(f'   sid:   {sid}')
print(f'   author: @{result["author"]}')
print(f'   images: {result["image_count"]}')
print(f'   translated: {result["translated"]}')

# --out 模式:复制过去
if args.out:
    import shutil
    shutil.copy(out_file, args.out)
    print(f'   copied to: {args.out}')

# 上传到 jcloud
if args.upload_jcloud:
    import paramiko
    if not JCLOUD_PWD:
        print('ERROR: JCLOUD_PWD 未设置(请写入本地 .env)', file=sys.stderr)
        sys.exit(1)
    print(f'\n[upload] 连接到 {JCLOUD_USER}@{JCLOUD_HOST} ...')
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(JCLOUD_HOST, username=JCLOUD_USER, password=JCLOUD_PWD)
    sftp = c.open_sftp()

    # 1. HTML
    remote_html = f'{JCLOUD_ARTICLES_DIR}/article_{sid}.html'
    print(f'  [1/2] 上传 article_{sid}.html ({out_file.stat().st_size:,} bytes)')
    sftp.put(str(out_file), remote_html)
    sftp.chmod(remote_html, 0o664)  # group writable so www-data can manage it

    # 2. assets dir(可能不存在如果没图片)
    if assets_dir.exists():
        n_imgs = sum(1 for _ in assets_dir.iterdir())
        remote_assets = f'{JCLOUD_ARTICLES_DIR}/assets/{sid}'
        print(f'  [2/2] 上传 assets/{sid}/ ({n_imgs} 文件)')
        # 远端先建目录
        try: sftp.mkdir(remote_assets)
        except IOError: pass
        for f in assets_dir.iterdir():
            remote_path = f'{remote_assets}/{f.name}'
            sftp.put(str(f), remote_path)
            sftp.chmod(remote_path, 0o664)
    else:
        print(f'  [2/2] 无 assets 目录,跳过')

    sftp.close()

    # 3. chown 给 www-data(让 articles service 能删)
    # 用已开 SSH 连接调 chown,失败不影响主流程(articles service 还会自己防御 chmod)
    try:
        chown_paths = [remote_html]
        if assets_dir.exists():
            chown_paths.append(remote_assets)
        chown_cmd = 'chown -R www-data:www-data ' + ' '.join(chown_paths)
        stdin, stdout, stderr = c.exec_command(chown_cmd)
        err = stderr.read().decode().strip()
        if err:
            print(f'  [3/3] chown warning: {err}')
        else:
            print(f'  [3/3] chown www-data OK ({len(chown_paths)} paths)')
    except Exception as e:
        print(f'  [3/3] chown failed (non-fatal): {e}')

    c.close()
    public_url = f'https://buumicloud.com.cn/articles/article_{sid}.html'
    print(f'\n✅ 上传完成!')
    print(f'   公开 URL: {public_url}')
