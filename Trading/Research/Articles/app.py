"""Articles 服务 - Flask backend for buumicloud.com.cn/articles

简化版:只做 list + delete + health。拉取/翻译工作全在本地 PC 完成,scp 上传。
- GET  /api/list     -> 所有文章元数据 JSON
- POST /api/delete   -> {sid, password} 删文章(密码 = ARTICLES_PASSWORD env)
- GET  /api/health   -> 健康检查
"""
import os, sys, shutil, stat
from pathlib import Path

# 拉 articles_lib(只为了 list_articles)
sys.path.insert(0, '/opt/articles')
from flask import Flask, request, jsonify
from dotenv import load_dotenv
load_dotenv('/opt/articles/.env')

from articles_lib import list_articles

app = Flask(__name__)

ARTICLES_DIR = Path('/var/www/articles')
ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

# 从 /opt/articles/.env 读;缺失则 delete 直接 401,不用默认密码放行
PASSWORD = os.environ.get('ARTICLES_PASSWORD', '')


@app.route('/api/list')
def api_list():
    return jsonify(list_articles(ARTICLES_DIR))


@app.route('/api/delete', methods=['POST'])
def api_delete():
    data = request.get_json(silent=True) or {}
    sid = (data.get('sid') or '').strip()
    pwd = (data.get('password') or '').strip()
    if not sid:
        return jsonify({'error': 'sid required'}), 400
    if pwd != PASSWORD:
        return jsonify({'error': 'password incorrect'}), 401

    deleted = []
    html_file = ARTICLES_DIR / f'article_{sid}.html'
    if html_file.exists():
        # 防御性 chmod: 老文件可能是 root:root 0o644, www-data 删不动
        try:
            os.chmod(html_file, 0o664)
        except PermissionError:
            pass
        html_file.unlink()
        deleted.append(str(html_file))

    assets_dir = ARTICLES_DIR / 'assets' / sid
    if assets_dir.exists():
        # 防御性 chmod 整树: shutil.rmtree 不允许 PermissionError
        def _add_write_perms(p, exc_info):
            if exc_info[0] is PermissionError:
                try:
                    os.chmod(p, 0o666)
                    os.chmod(str(Path(p).parent), 0o775)
                except Exception:
                    pass
            os.unlink(p)
        shutil.rmtree(assets_dir, onexc=_add_write_perms)
        deleted.append(str(assets_dir))

    if not deleted:
        return jsonify({'error': 'article not found'}), 404
    return jsonify({'ok': True, 'deleted': deleted})


@app.route('/api/health')
def api_health():
    return jsonify({
        'ok': True,
        'articles_count': len(list(ARTICLES_DIR.glob('article_*.html'))),
        'mode': 'static-readonly',
    })


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
