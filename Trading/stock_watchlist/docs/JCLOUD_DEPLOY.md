# Stock Watchlist 部署到 jcloud 的踩坑汇总

_最后更新：2026-07-04_

本文档记录 2026-07-04 把 stock_watchlist 部署到 jcloud (111.228.51.56) 期间踩过的所有坑、修复方式、以及为后续维护沉淀的经验。每条坑包含：**症状 → 根因 → 修复 → 教训**。

> **目标环境**：jcloud 上 `/opt/stock_watchlist/`，通过 `https://buumicloud.com.cn/watchlist/` 暴露。Flask 进程监听 `127.0.0.1:5181`，systemd 服务名 `stock-watchlist.service`。本地开发仓库存放于 `D:\WorkSpace\Trading\stock_watchlist\`。

---

## 坑清单（按发生顺序）

### 坑 1：watchlist 反代 location 被注释压扁
- **症状**：访问 `https://buumicloud.com.cn/watchlist/` 返回 nginx 默认 404 页面；`/watchlist/api/health` 也 404。
- **根因**：`/etc/nginx/sites-enabled/unified` line 364 原本是注释 `# ===== Stock Watchlist =====    location /watchlist/ { proxy_pass ...; ... }`，**整行被当作注释**，nginx 跳过整个 location 块 → 没有任何 location 匹配 `/watchlist/` → fallthrough 404。
- **修复**：把 `===== Stock Watchlist =====` 后加换行，让 `location /watchlist/ {...}` 起独立行（不再被 inline 进 `#` 注释行）。
- **教训**：nginx 注释 `#` 之后**一定要换行**，否则整行（直到行尾）都被吞。如果 location 块前面有"装饰性"中文标题（如 `# ===== xxx =====`），必须独立成行，后面 location 另起一行。

### 坑 2：proxy_pass 没 trailing slash，Flask 收不到正确路径
- **症状**：修完坑 1 后，`https://buumicloud.com.cn/watchlist/api/health` 仍然 404，但**是 Flask 自己的 404**（HTML body 含 `<title>404 Not Found</title>`，不是 nginx 那个）。
- **根因**：`proxy_pass http://127.0.0.1:5181;`（**没** trailing slash）会让 nginx 把 `/watchlist/api/health` **完整**转给 Flask。Flask blueprint 注册的是 `@bp.route("/api/health")`，找不到 `/watchlist/api/health` 这个 path → 404。
- **修复**：改成 `proxy_pass http://127.0.0.1:5181/;`（**带** trailing slash），nginx 把 `/watchlist/` 前缀 strip 掉，Flask 收到 `/api/health` → 200。
- **教训**：Flask blueprint mount point 反代 → 用 trailing slash **strip 前缀**；具体规则见坑 5。

### 坑 3：jcloud 上 watchlist.db 是空 db
- **症状**：API 都通，但 `/api/sectors` 返回 `{"data":[]}`；`/api/sectors/102` 也返回空（连 AIDC 板块都不存在）。
- **根因**：jcloud 上的 `/opt/stock_watchlist/data/watchlist.db` 是 69632 bytes 的空 db（0 sectors / 0 stocks / 0 sector_stocks），而本地 db 是 204800 bytes 的满数据（399 stocks / 31 sectors / 486 sector_stocks）。原因：`import_xlsx.py` 没在 jcloud 上跑过（或者跑挂了），data/lists/ 下的 26 个 xlsx 文件从未被导入到 jcloud db。
- **修复**：直接用本地 db 覆盖 jcloud db（流程见坑 4）。本地 db 是 single source of truth (SSOT)，jcloud db 是 read-only 副本。
- **教训**：jcloud 部署 db 数据同步需要明确流程。建议写 `scripts/push_watchlist_db.ps1` 把 5 步固化下来（坑 4）。

### 坑 4：db 同步流程的 5 个小坑
- **症状**：直接把本地 db scp 上去，覆盖后 jcloud service 仍在用旧 db 句柄。
- **根因 / 修复（正确流程）**：
  1. **sftp-put 到 `.new`**：本地 `D:\WorkSpace\Trading\stock_watchlist\data\watchlist.db` (204800 bytes, md5 `5d090afd59f6c0763dfbcb3a35f07679`) → jcloud `/opt/stock_watchlist/data/watchlist.db.new`（先到 `.new`，不直接覆盖原文件做 atomic fallback）。
  2. **停 service**：`systemctl stop stock-watchlist.service` 释放 db 句柄 + SQLite lock。
  3. **备份原 db**：`cp watchlist.db watchlist.db.bak_empty_<ts>` (69632 bytes 原空 db)。**坑**：PowerShell `$(date +%Y%m...)` 把 date 当 Get-Date 命令，备份文件名后缀变空字符串 `watchlist.db.bak_empty_`，要事后 `mv` 改名。
  4. **原子覆盖**：`mv watchlist.db.new watchlist.db`。
  5. **启 service**：`systemctl restart stock-watchlist.service`。
- **附加坑**：
  - **本地 db 被锁**：本地进程 PID 17216 `python app.py` 持有本地 db 文件句柄，PowerShell `Get-FileHash` 报"文件正由另一进程使用"。**修法**：用 python `open(DB, 'rb').read()` 绕开（SQLite 允许并发读）。或者先停本地 app.py 再 hash。
  - **WAL/SHM 残留**：理论上应该有 `watchlist.db-wal` / `watchlist.db-shm` 残留，但 service 启动后没多久就被 stop，没机会写 WAL，所以这次没有。要养成"停 service 后清 -wal/-shm 再覆盖"的习惯。

### 坑 5：proxy_pass trailing slash 方向（最易错）
- **症状**：`https://buumicloud.com.cn/static/app.js` 走 nginx 反代返回 404（Flask 404），但直接访问 `http://127.0.0.1:5181/static/app.js` 是 200。
- **根因**：`location /static/ { proxy_pass http://127.0.0.1:5181/; }` 中 `proxy_pass` 的 **trailing slash** 决定了 nginx 是否 strip location prefix。
  - **有 slash** → nginx 把 `/static/app.js` 转给 Flask 时变成 `/app.js`（strip 掉 `/static/`）→ Flask 没这个路由 → 404。
  - **无 slash** → nginx 保留完整 path `/static/app.js` → Flask 默认 `/static/<path>` 路由 200。
- **修复**：`location /static/ { proxy_pass http://127.0.0.1:5181; }` **去掉 trailing slash**。
- **通用规则**：
  - **Flask 全局静态资源** (`/static/`, `/favicon.ico`, ...) → `proxy_pass http://127.0.0.1:5181;`（**无 slash**，保留完整 path）
  - **Flask blueprint mount point** (`/watchlist/`, `/admin/`, ...) → `proxy_pass http://127.0.0.1:5181/;`（**有 slash**，strip 前缀让 blueprint 注册的 `@bp.route("/")` 能匹配）
- **教训**：这是 nginx 反代 Flask 的最易错点。**先看 Flask blueprint 注册的 path**，决定 nginx 是否需要 strip 前缀。

### 坑 6：`/static/` 和 `/api/` location 缺失 → 全部 fallthrough 404
- **症状**：`https://buumicloud.com.cn/static/app.js` → 404；`https://buumicloud.com.cn/api/sectors` → 404。但 `https://buumicloud.com.cn/watchlist/static/app.js` 和 `/watchlist/api/sectors` 都 200。
- **根因**：index.html 里 `<script src="/static/app.js">` 和 `<link href="/static/style.css">` 用**绝对路径不带前缀**；app.js 内部 `api('/api/sectors')`、`api('/api/sectors/${id}/tree')` 也都是**绝对路径不带前缀**。unified 配置里**只有** `location /watchlist/`，**没有** `location /static/` 也没有 `location /api/` → 所有 `/static/*` 和 `/api/*` 落到 nginx fallthrough → 404。
- **修复**：在 unified 的 443 server block 里加 `location /static/` 和 `location /api/` 两个反代（都用坑 5 的"无 slash"规则）。
- **教训**：部署 Flask 应用时如果用了 `/prefix/` 反代，所有 Flask 引用的资源路径（`/static/`、`/api/`、未来可能加的 `/metrics/` 等）都得在 nginx 加对应 location。最稳的写法是把所有前缀路径都在同一 server block 加 location 反代，**无论前端引不引用**。

### 坑 7：nginx access log 里 3096 bytes 不是 404 页面
- **症状**：第一次看 nginx access log 显示 iPhone 访问 `/watchlist/` 返回 200 3096 bytes，以为是 nginx 自己的 404 页面。
- **根因**：3096 bytes 是 **gzip 压缩后**的 transfer size（实际未压缩 11399 bytes）。nginx 默认对 HTML/JS/CSS 启用 gzip。
- **教训**：debug nginx 响应时**先看 Content-Length 配合 Accept-Encoding**。`curl --compressed` 或加 `-H 'Accept-Encoding: identity'` 拿到未压缩 body。

### 坑 8：行情页空白（前端问题，非后端）
- **症状**：手机访问能选板块、能看到 AIDC 8 只个股列表，但点击个股进入详情页后右侧行情/走势图/分时 K线**什么都显示不了**。
- **后端状态**：所有行情接口都 200 OK：
  - `/api/stocks/sz.002929` → 200, 569 bytes
  - `/api/stocks/sz.002929/minute` → 200, 27420 bytes
  - `/api/stocks/sz.002929/kline` → 200, 38481 bytes
  - `/api/sectors/102/tree` → 200, 5649 bytes
- **最可能的根因**：
  1. **`echarts.min.js` 加载失败**：index.html 里 `<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>` 从 jsdelivr CDN 加载，手机网络环境如果屏蔽 jsdelivr → echarts 全局变量没定义 → `echarts.init is not a function` → 整个 chart 渲染挂。
  2. **`refreshChart` 早 return**：`if (state.chartMode !== 'minute') return; if (!state.chartInstance) return;` 两道闸门都让 refreshChart 不工作。但这是 UI 自身的代码逻辑，不是部署问题。
- **修复方向**：
  - 把 echarts.min.js 下载到 `static/echarts.min.js`，HTML 引用 `./static/echarts.min.js`（避免依赖外网 CDN）
  - 或者在 nginx 加白名单，把 jsdelivr 走代理
- **教训**：生产环境**慎用第三方 CDN**，要么本地化要么走自家代理。

---

## nginx 反代 Flask 的通用模板（沉淀）

把 stock_watchlist 部署到 `/watchlist/` 子路径下，nginx 443 server block 内需要的最小 location 集合：

```nginx
# 全局静态资源（保留完整 path）
location /static/ {
    proxy_pass http://127.0.0.1:5181;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 120s;
}

# Flask API（保留完整 path）
location /api/ {
    proxy_pass http://127.0.0.1:5181;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 120s;
}

# Flask blueprint mount point（strip 前缀）
location /watchlist/ {
    proxy_pass http://127.0.0.1:5181/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 120s;
}
location /watchlist {
    return 301 /watchlist/;
}
```

**关键决策点**：
- `/static/` `/api/` 用 `proxy_pass http://127.0.0.1:5181;` **无 trailing slash**（保留 path）
- `/watchlist/` 用 `proxy_pass http://127.0.0.1:5181/;` **有 trailing slash**（strip 前缀）

---

## db 数据同步脚本（沉淀）

建议写到 `scripts/push_watchlist_db.ps1`：

```powershell
# push_watchlist_db.ps1
# 流程：sftp-put 到 .new → 停 service → 备份 → 覆盖 → 启 service

$localDB = 'D:\WorkSpace\Trading\stock_watchlist\data\watchlist.db'
$remoteDB = '/opt/stock_watchlist/data/watchlist.db'
$remoteNew = '/opt/stock_watchlist/data/watchlist.db.new'
$ts = Get-Date -Format 'yyyyMMdd_HHmm'

# 1. sftp-put 到 .new
python D:\WorkSpace\openclaw_env\skills\ssh\scripts\ssh_exec.py sftp-put $localDB $remoteNew

# 2. 停 service
python D:\WorkSpace\openclaw_env\skills\jcloud\scripts\jcloud.py stop stock-watchlist

# 3. 备份 + 覆盖
python D:\WorkSpace\openclaw_env\skills\jcloud\scripts\jcloud.py exec "cp $remoteDB $remoteDB.bak_empty_$ts && mv $remoteNew $remoteDB"

# 4. 启 service
python D:\WorkSpace\openclaw_env\skills\jcloud\scripts\jcloud.py restart stock-watchlist

# 5. 验证
python D:\WorkSpace\openclaw_env\skills\jcloud\scripts\jcloud.py exec "curl -sk https://buumicloud.com.cn/watchlist/api/health"
```

---

## 当前 jcloud 状态（截至 2026-07-04）

- **watchlist.db**：`/opt/stock_watchlist/data/watchlist.db` (204800 bytes)，399 stocks / 31 sectors / 486 sector_stocks / 16 notes
- **service**：`stock-watchlist.service` PID 3707300 起，监听 `127.0.0.1:5181`，active running
- **nginx locations**：`/watchlist/`、`/static/`、`/api/` 都已加反代
- **lists/ 目录**：26 个 xlsx 已删（baumi 决策，本地保留作为 import 源）
- **备份**：原空 db 在 `/opt/stock_watchlist/data/watchlist.db.bak_empty_20260704_1609`
- **遗留问题**：
  - `unified.bak.1782566694` 还在 `sites-enabled/` 触发 `conflicting server name` warning（不影响服务）
  - `articles/` 相关 location 缩进 0（line 420 附近）在 server block 外，nginx 警告但不影响
  - 行情页 echarts.min.js 走 jsdelivr CDN，手机可能加载失败

---

## 待办（下一步 baumi 决策）

- [ ] 行情页 echarts.min.js 改本地化
- [ ] `unified.bak.1782566694` 挪进 `.bak_archive/`
- [ ] 把 push_watchlist_db.ps1 写完整
- [ ] `cd2` 后端 502 问题排查（看 jcloud `:7860` 上游）