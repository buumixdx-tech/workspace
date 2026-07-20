# 📚 Articles

X / Twitter 长文(X Article)抓取 → 中文翻译 → 上传 jcloud 公开分享。

```
本地 PC                                          jcloud (111.228.51.56)
┌──────────────────┐                            ┌──────────────────────────┐
│ build_article.py │  ── scp ──>  /var/www/    │  nginx → /articles/      │
│  + articles_lib  │              articles/      │    ↳ 静态 serve HTML+    │
│  + ANTHROPIC_*   │                            │      assets              │
└──────────────────┘                            │  nginx → /articles/api/  │
       │                                        │    ↳ Flask: list/delete  │
       │ 调 MiniMax M3                           │                          │
       ▼                                        └──────────────────────────┘
  fxtwitter API
```

## 架构分工

| 工作 | 在哪跑 | 原因 |
|---|---|---|
| 拉 X article + 下载图片 | 本地 | jcloud 出口网络对 fxtwitter 不稳 |
| 中文翻译(调 LLM) | 本地 | API key 留在本地,翻译是耗时操作 |
| HTML 渲染 | 本地 | `articles_lib.blocks_to_html` |
| scp 上传 HTML+assets | 本地 | `build_article.py --upload-jcloud` |
| 列表/搜索/分享 | jcloud | 纯静态 nginx serve |
| 删除文章 | jcloud | Flask API + 密码 |

## 快速开始

### 本地 PC

```bash
# 1. 装依赖(都已预装)
pip install python-docx anthropic python-dotenv paramiko

# 2. 写 .env(本目录)
cat > .env <<EOF
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
ANTHROPIC_AUTH_TOKEN=sk-cp-xxx...
ANTHROPIC_MODEL=MiniMax-M3
JCLOUD_HOST=111.228.51.56
JCLOUD_USER=root
JCLOUD_PWD=xxx
ARTICLES_PASSWORD=xxx
EOF

# 3. 拉 + 翻译 + 上一气呵成(默认不翻译,需要翻译才传 --translate)
python build_article.py -u "https://x.com/<user>/status/<id>" --upload-jcloud --translate

# 跳过翻译(只拉原文,默认行为)
python build_article.py -u "..." --upload-jcloud

# 只本地生成,不上传
python build_article.py -u "..."
```

### jcloud 部署(首次)

```bash
python deploy_to_jcloud.py    # 一键完成 systemd + nginx + UI
python redeploy.py            # 增量重部署(只推 app.py + index.html)
```

## 文件结构

```
D:\WorkSpace\Trading\Research\Articles\
├── articles_lib.py          # 核心库(供 build_article.py + jcloud app.py 共享)
├── build_article.py         # 本地 CLI 入口
├── app.py                   # jcloud Flask app(只读 list + 受控 delete)
├── index.html               # jcloud UI(浏览 + 管理)
├── articles.service         # systemd unit(/etc/systemd/system/)
├── nginx_snippet.conf       # nginx location 段
├── deploy_to_jcloud.py      # 首次部署脚本
├── redeploy.py              # 增量重部署
├── .env                     # 本地凭证(不进 git)
└── .gitignore
```

jcloud 上对应:

```
/opt/articles/
├── app.py
├── articles_lib.py
├── articles.service
└── .env                     # ARTICLES_PASSWORD=xxx(管理密码)

/var/www/articles/           # nginx 直接 serve
├── index.html
├── article_<sid>.html
└── assets/<sid>/img_xx.jpg
```

## articles_lib 公开 API

```python
from articles_lib import (
    fetch_x_article,           # 调 fxtwitter API
    download_images,           # 下载图片到 output_dir/assets/<sid>/
    translate_x_article,       # 调 MiniMax M3 翻译 blocks + title
    blocks_to_html,            # Draft.js blocks → HTML 字符串
    build_article,             # 上面四个串起来,返回 {path, title, sid, ...}
    list_articles,             # 扫描 output_dir/article_*.html 返回元数据列表
)
```

`build_article` 流程:

```python
result = build_article(
    url='https://x.com/JoeAnima/status/2071782733718958348',
    translate=True,
    output_dir=Path('/var/www/articles'),
)
# → {
#     'path': Path('.../article_2071782733718958348.html'),
#     'title': '玻璃基板:资金流向的秩序',
#     'sid': '2071782733718958348',
#     'author': 'damnang2',
#     'translated': True,
#     'image_count': 5,
# }
```

## 翻译实现要点

```python
# articles_lib.translate_x_article
BATCH = 10            # 每次 10 个 block(平衡速度与稳定性)
MAX_TOKENS = 8192     # 给 extended thinking + 中文输出同时留足预算

# 三步:
# 1. 翻译 title(单独请求)
# 2. 翻译 blocks(分批,空段用 /EMPTY/ 占位)
# 3. 每个 batch 重试 1 次,部分行数对得上也接受
#    (n_match > 0 即可,缺的最后几段保留英文)
```

**Prompt 关键规则**:
- 保留 ticker、产品名、人名、URL、emoji 不译(NVDA / AMD / Corning 等)
- 输出 `/EMPTY/` 表示空行
- 严格按 `[1] [2] [3]` 顺序逐行输出

## jcloud Flask API

| 方法 | 路径 | 说明 | 鉴权 |
|---|---|---|---|
| `GET` | `/api/list` | 文章元数据 JSON 列表 | 无 |
| `POST` | `/api/delete` | `{sid, password}` 删除文章 | 需 `ARTICLES_PASSWORD` |
| `GET` | `/api/health` | 健康检查 | 无 |

`/api/list` 返回结构:

```json
[
  {
    "sid": "2071782733718958348",
    "title": "🚨 康宁,已经不再是一家材料公司了。...",
    "author": "JoeAnima",
    "date": "2026-06-30",
    "translated": true,
    "has_images": true,
    "url": "/articles/article_2071782733718958348.html",
    "mtime": 1719750000.0
  }
]
```

## nginx 配置

注入到 `/etc/nginx/sites-enabled/unified` 的最后:

```nginx
location /articles/ {
    alias /var/www/articles/;
    try_files $uri $uri/ =404;
    index index.html;
    autoindex off;
}

location /articles/api/ {
    proxy_pass http://127.0.0.1:5000/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 180s;
}
```

`location /articles/` 直接 serve 静态(快),`location /articles/api/` 转发到 Flask on `127.0.0.1:5000`。

## systemd 守护

`/etc/systemd/system/articles.service`:

```ini
[Service]
User=www-data
WorkingDirectory=/opt/articles
EnvironmentFile=/opt/articles/.env
ExecStart=/usr/bin/python3 /opt/articles/app.py
Restart=always
```

```bash
systemctl status articles
systemctl restart articles
journalctl -u articles -f
```

## UI 截图描述(无图)

- 顶部:渐变色标题 "📚 Articles",副标题 "X / Twitter 长文收藏与翻译"
- 主面板:搜索框 + 刷新按钮 + 管理状态点(绿/灰) + 启用/退出管理按钮
- 文章卡片:每篇一卡,显示日期 / 作者 / 翻译标签 / 含图标签 / 复制链接 / 删除按钮(管理模式下)
- 管理密码弹窗:点"启用管理"输入密码,localStorage 持久化,后续操作免重复输入
- 删除二次确认:弹窗,防误删

## 已知坑

1. **MiniMax M 系列的 extended thinking** 会和 text block **共用 max_tokens 预算**。`MAX_TOKENS=8192` + `BATCH=10` 是经过实测的稳态参数;小于这个值会偶发吞行。
2. **fxtwitter entityMap** 返回 list 不是 dict,代码两种都兼容(`isinstance(em, dict)` 分支)。
3. **atomic block** 的 `text` 是空字符串,旧版会跳过,导致图片/表格/emoji 丢失。`block_to_html` 必须先看 `btype == 'atomic'`,只渲染 entity。
4. **DIVIDER entity** `data` 是空 dict,需要在 entity 处理分支里特殊判断。
5. **emoji 嵌入正文** 时(unstyled block 同时含 entity + 短文字),不能直接用 text 替换,要分别处理 inline emoji 和 block-level 图片。
6. **jcloud 出口网络** 对 `api.fxtwitter.com` 偶发超时,这就是为什么"翻译工作必须本地做"。

## 依赖

```txt
# 本地
anthropic>=0.40
python-dotenv
python-docx
paramiko

# jcloud(已预装)
flask>=3.0
python-dotenv
requests
```

## 凭证管理

- `ANTHROPIC_*` 只在本地 `.env`(翻译在本地跑,jcloud 不需要)
- `ARTICLES_PASSWORD` 本地 `.env`(供 deploy 脚本读取)+ jcloud `/opt/articles/.env`(deploy 写入,app.py 读)
- 两者都加进 `.gitignore`

## 命令速查

```bash
# 本地
python build_article.py -u <URL> --upload-jcloud              # 拉+上传(默认不翻译)
python build_article.py -u <URL> --upload-jcloud --translate # 拉+翻译+上传
python build_article.py -u <URL> -o D:\out.html               # 自定义输出路径

# jcloud
systemctl status articles
systemctl restart articles
curl https://buumicloud.com.cn/articles/api/health
curl https://buumicloud.com.cn/articles/api/list | python -m json.tool

# 重新部署
python redeploy.py              # 增量(推 app.py + index.html)
python deploy_to_jcloud.py      # 全量(首次)
```
