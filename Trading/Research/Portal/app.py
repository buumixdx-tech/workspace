"""buumicloud 应用门户(主域根入口)

职责:
- GET /login      → 自定义 HTML 登录页(深色 UI)
- POST /api/login → 验证 htpasswd,下发 JWT cookie,重定向到 /
- POST /api/logout → 清 cookie,重定向到 /login
- GET /           → 门户主页(未登录 302 /login)
- GET /health     → JSON 状态聚合

认证:
- 用户密码存于 /etc/nginx/.htpasswd_rag(apache md5)
- 通过 passlib.apache.HtpasswdFile 校验
- 登录成功后发 JWT,7 天有效(写 httpOnly cookie)
- JWT secret 从 .env 读(无 secret 时随机生成但 warn)
"""
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
import requests
from cachetools import TTLCache
from flask import Flask, jsonify, redirect, render_template, request
from passlib.apache import HtpasswdFile
from requests.auth import HTTPBasicAuth

app = Flask(__name__)

# --- 配置 ---
HTPASSWD_PATH = os.environ.get('HTPASSWD_PATH', '/etc/nginx/.htpasswd_rag')
JWT_SECRET = os.environ.get('JWT_SECRET', '')
JWT_ALGO = 'HS256'
JWT_TTL_DAYS = 7
COOKIE_NAME = 'portal_token'

if not JWT_SECRET:
    # 不强 fail:开发期方便,但生产务必设
    JWT_SECRET = secrets.token_urlsafe(32)
    print(f'[WARN] JWT_SECRET 未设置,使用随机值(重启后失效).请在 /opt/portal/.env 设 JWT_SECRET=...', flush=True)

# --- 探测池 + 缓存(全局,跨请求复用) ---
pool = ThreadPoolExecutor(max_workers=10)
cache = TTLCache(maxsize=32, ttl=5)

# basic auth 凭据(用于探测 state/rag-messages-api/mycloud-api)
RAG_USER = os.environ.get('RAG_USER', '')
RAG_PWD = os.environ.get('RAG_PASSWORD', '')
BASIC_AUTH = HTTPBasicAuth(RAG_USER, RAG_PWD) if RAG_USER else None


# (key, name, url, health_url, needs_auth)
APPS = [
    ("articles",  "Articles",     "https://buumicloud.com.cn/articles/",  "https://buumicloud.com.cn/articles/api/health", False),
    ("md",        "MD Viewer",    "https://buumicloud.com.cn/md/",        None,                                            False),
    ("watchlist", "Watchlist",    "https://buumicloud.com.cn/watchlist/", "https://buumicloud.com.cn/api/health",          False),
    ("feishu",    "飞书消息搜索",  "https://buumicloud.com.cn/feishu/",    None,                                            False),
    ("mycloud",   "我的资料库",    "https://buumicloud.com.cn/my/",        "https://buumicloud.com.cn/my/docs",             False),
    ("state",     "RAG Dashboard","https://buumicloud.com.cn/state/",     "https://buumicloud.com.cn/state/",              True),
    ("asset",     "资产盘点",      "https://asset.buumicloud.com.cn/asset/", "https://asset.buumicloud.com.cn/asset/",     False),
    ("cd2",       "CloudDrive2",  "https://cd2.buumicloud.com.cn/",       "https://cd2.buumicloud.com.cn/",                False),
    ("vc",        "VoceChat",     "https://vc.buumicloud.com.cn/",        "https://vc.buumicloud.com.cn/",                 False),
]


# ---------- 状态探测 ----------

def probe(url, auth=None, timeout=2):
    if not url:
        return 'grey'
    try:
        r = requests.get(url, timeout=timeout, auth=auth, verify=True, allow_redirects=False)
        return 'green' if r.status_code in (200, 401) else 'grey'
    except Exception:
        return 'grey'


def probe_one(key, url, health_url, needs_auth):
    if key in cache:
        return cache[key]
    auth = BASIC_AUTH if needs_auth else None
    s = probe(health_url or url, auth=auth)
    cache[key] = s
    return s


# ---------- 认证 ----------

def verify_htpasswd(user, password):
    """返回 bool。htpasswd 文件不存在 / 用户不存在 / 密码错 都返回 False。"""
    try:
        ht = HtpasswdFile(HTPASSWD_PATH)
        return ht.verify(user, password) or False
    except Exception:
        return False


def make_token(user):
    payload = {
        'sub': user,
        'iat': datetime.now(timezone.utc),
        'exp': datetime.now(timezone.utc) + timedelta(days=JWT_TTL_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def parse_token(token):
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload.get('sub')
    except Exception:
        return None


def login_required(f):
    """未登录 → 重定向到 /login(带 next 参数)"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = parse_token(request.cookies.get(COOKIE_NAME))
        if not user:
            return redirect(f'/login?next={request.path}')
        return f(*args, **kwargs)
    return wrapper


# ---------- 路由 ----------

@app.route('/login', methods=['GET'])
def login_page():
    # 已登录直接跳门户
    if parse_token(request.cookies.get(COOKIE_NAME)):
        return redirect('/')
    return render_template('login.html', next=request.args.get('next', '/'))


@app.route('/api/login', methods=['POST'])
def api_login():
    user = (request.form.get('username') or '').strip()
    pw = request.form.get('password') or ''
    next_url = request.form.get('next') or '/'
    if not user or not pw or not verify_htpasswd(user, pw):
        # 重新渲染登录页 + 错误提示(用 ?error=1 不暴露具体哪步错)
        return render_template('login.html', next=next_url, error='账号或密码错误'), 401
    token = make_token(user)
    resp = redirect(next_url)
    # httpOnly + SameSite=Lax;Secure 留给 nginx 加(它在前面已经是 HTTPS)
    resp.set_cookie(COOKIE_NAME, token, max_age=JWT_TTL_DAYS * 86400, httponly=True, samesite='Lax', path='/')
    return resp


@app.route('/api/logout', methods=['POST'])
def api_logout():
    resp = redirect('/login')
    resp.delete_cookie(COOKIE_NAME, path='/')
    return resp


@app.route('/')
@login_required
def index():
    user = parse_token(request.cookies.get(COOKIE_NAME))
    apps_for_template = [{
        'key': k, 'name': n, 'url': u, 'auth': a
    } for k, n, u, _, a in APPS]
    return render_template('index.html', apps=apps_for_template, user=user)


@app.route('/health')
def health():
    """聚合状态:并发探测所有应用,5 秒缓存(供前端 fetch)

    注:未加 @login_required —— 浏览器带 cookie 自动通过;curl 测试时用 cookie 也行。
    """
    futures = {
        k: pool.submit(probe_one, k, u, health_url, needs_auth)
        for k, _, u, health_url, needs_auth in APPS
    }
    statuses = {k: f.result() for k, f in futures.items()}
    return jsonify(statuses)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=7080, debug=False)
