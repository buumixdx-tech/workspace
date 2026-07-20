# stock_watchlist

个人 / 小团队用的 A 股 + 港股 + 美股 watchlist。Flask 后端 + 浏览器前端,SQLite 存板块 / 股票 / 笔记元数据,后台 daemon 拉行情 + 实时算板块指标。

## 能力

- **板块管理** — 树形结构,标签分 `core` / `focus` / `observation` 三级,支持拖拽排序
- **实时行情** — A 股走 eltdx (3s tick),HK/US 走 yfinance (30s tick),板块指标在 quote 刷新后立即重算
- **个股详情** — quote + 1m K 线 + 公司画像 (profile 5min 拉一次)
- **笔记** — 按股票归档,带 tags
- **导入** — xlsx 板块列表 (`data/lists/*.xlsx`) 通过 `import_xlsx.py` 灌进 db

## 技术栈

- **后端**: Python 3.x + Flask 3.x
- **DB**: SQLite (单文件,`data/watchlist.db`)
- **行情源**:
  - A 股: [eltdx](https://pypi.org/project/eltdx/) (`src/core.py:get_client`)
  - HK / US: [yfinance](https://pypi.org/project/yfinance/) 批量 spark 端点 (`src/yf.py`,`BATCH_SIZE=15`)
- **前端**: 静态 HTML + JS (无框架),`static/` + `templates/`

## 启动

### 本地 (Windows)

```cmd
:: 自动建 venv + 装依赖 + 启 Flask
start.bat
```

或手动:

```cmd
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app.py
```

默认监听 `http://127.0.0.1:5181`,改端口见 `config.toml`。

### jcloud (生产)

部署 + 踩坑见 [`docs/JCLOUD_DEPLOY.md`](docs/JCLOUD_DEPLOY.md)。

- systemd 服务名: `stock-watchlist.service`
- 反代入口: `https://buumicloud.com.cn/watchlist/`
- jcloud 路径: `/opt/stock_watchlist/`
- 本地 db 是 SSOT,jcloud db 用本地覆盖同步 (见 JCLOUD_DEPLOY 坑 3-4)

## 项目结构

```
stock_watchlist/
├── app.py                  # Flask 入口 + _bootstrap (启 db + 3 cache + aggregator)
├── routes.py               # 所有 API 路由 (sector / stock / note / kline)
├── cli.py                  # 命令行工具
├── config.toml             # 端口 / TDX 配置
├── start.bat               # Windows 一键启动
├── import_xlsx.py          # 板块 xlsx 灌库 (末尾通知 daemon recompute)
├── migrate_yf_format.py    # yf 数据格式迁移工具
├── requirements.txt
│
├── src/                    # 核心模块
│   ├── db.py               # SQLite CRUD (stocks / sectors / sector_stocks / notes / sector_relations)
│   ├── core.py             # 公共工具 (TdxClient, code normalize, quote remap)
│   ├── config_loader.py    # config.toml 读取
│   ├── quote_cache.py      # A 股 quote 后台缓存 (3s tick,写入时算 limit_flag)
│   ├── profile_cache.py    # 公司画像缓存 (5min tick)
│   ├── yf_cache.py         # HK/US quote 后台缓存 (30s tick,提供 snapshot())
│   ├── yf.py               # yfinance 包装 (batch spark)
│   ├── indices_cache.py    # 6 个固定指数后台缓存 (3s tick,eltdx + yfinance 双源)
│   ├── sector_aggregator.py# 板块指标聚合 (订阅 QuoteCache + ProfileCache 双 hook)
│   ├── sectors.py          # 板块业务逻辑
│   ├── stocks.py           # 股票业务逻辑
│   ├── limit_price.py      # 涨跌停价计算
│   ├── cache_invalidator.py# 统一 cache 失效入口 (C1)
│   └── errors.py           # 自定义 API 异常类 (C3)
│
├── data/
│   ├── watchlist.db        # 主 db (SSOT,本地)
│   ├── stock_watchlist.db  # 副本 (jcloud 同步用,见 JCLOUD_DEPLOY 坑 3)
│   ├── a_share_list.json   # A 股全代码缓存 (eltdx 用)
│   ├── lists/              # 板块 xlsx 列表 (AIDC, AI应用, AI电源, MLCC, OCS 等)
│   └── klines_1m/          # 1m K 线 JSON 文件 (按 code+date 分文件,见 src/limit_price.py 周边)
│
├── static/  templates/     # 前端 (无框架)
├── tests/                  # 单元 + 集成测试 (limit_price)
└── docs/
    ├── API.md              # 所有 /api/* 接口
    ├── JCLOUD_DEPLOY.md    # jcloud 部署踩坑汇总
    └── USER_SYSTEM.md      # ⚠️ 多用户 / 认证设计稿 (计划中,未实现)
```

## 关键模块

| 模块 | 职责 | 节奏 |
|---|---|---|
| `QuoteCache` (A 股) | eltdx 拉 watchlist 全 A 股 quote,内存 dict 缓存 | **3s** tick |
| `YfCache` (HK / US) | yfinance 批量 spark 拉 quote | **30s** tick |
| `IndicesCache` | 6 个固定指数 (上证/深成/科创 + 日经/KOSPI/台湾加权) | **3s** tick (A 股 eltdx + 海外 yfinance 双源并行) |
| `ProfileCache` | 公司画像 (市值 / PE / 行业) | **5min** tick |
| `SectorAggregator` | quote 刷新后重算板块涨跌幅 / contributors / top movers | event-driven,订阅 `QuoteCache.on_refresh` |

池子变更 (sector_stocks 增删) 触发 `QuoteCache.invalidate_pool()`,下次 tick 重载池子。单只失败 **60s cooldown** 避免反复打。

行情类 (quote / profile) **只存 latest 一条快照在内存,无持久化**。要历史自行落 parquet / DuckDB,不在本仓库职责内。

## 配置 (`config.toml`)

- `[server]` host / port,默认 `127.0.0.1:5181`
- `[tdx]` TDX 主机列表 (留空用 eltdx 内置池) / 超时 / 心跳间隔
- `[stocks]` A 股代码表缓存路径和刷新策略

## 文档

- [`docs/API.md`](docs/API.md) — 所有 `/api/*` 端点 + 请求 / 响应 schema + 错误码章节
- [`docs/JCLOUD_DEPLOY.md`](docs/JCLOUD_DEPLOY.md) — jcloud 部署踩坑汇总 (nginx / Flask / db 同步)

## 状态

- ✅ 单用户本地 + jcloud 部署,稳定运行
- ⏳ 行情历史持久化:未做;若需,建议 DuckDB sidecar (与 metadata 分文件,职责分清)

## 2026-07-07 修复日志

针对 API + 性能审查发现的 16 条本地相关问题,这一批全部修完:

### 正确性修复

| 编号 | 问题 | 修法 |
|------|------|------|
| C1 | 4 个 mutation path 不失效 A 股 cache 池子 | 抽 `src/cache_invalidator.py`,接到所有 mutation 端点 + Aggregator.recompute |
| C2 | `cache_coverage` 端点 sqlite3.connect 永不 close | 用 `with` 上下文 + 空 ids 兜底 |
| C3 | `@_safe` 把所有异常返 500 | 拆 `src/errors.py` 自定义异常,`ApiError` 子类返 400/404/409,其他仍 500 |
| I4 | ProfileCache refresh 不触发 SectorAggregator | `attach` 接 ProfileCache.on_refresh 双 hook |
| I5 | 笔记长度限制只在文档不在代码 | `api_create_note`/`api_update_note` 加 title ≤15 / body ≤300 / tags ≤10 |
| I11 | `import_xlsx.py` 灌库期间前端指标空 | 新增 `/api/admin/recompute` 端点,`import_xlsx` 末尾通知 daemon |

### 性能修复

| 编号 | 问题 | 修法 |
|------|------|------|
| C7 | 前端 3s tick 逐只股顺序 fetch | 新增 `/api/stocks/quotes` 批量端点(200 只上限),前端 `fetchQuotesBatch` 一次 HTTP |
| C8 | HK/US `api_stock_detail` 绕过 YfCache 直打 YF | 优先读 `YF_CACHE.get`,miss 才回退直打 |
| I2 | `_enrich_stocks` O(N²) code 匹配 | 用 `other_a_by_raw` dict 索引,O(N) |
| I3 | `api_stock_detail` A 股 cache miss 同步打 eltdx | 5s cooldown 锁,同 code 重复 miss 不重复打 |
| I6 | `_enrich_stocks` YF 分支串行读 cache | `YfCache.snapshot()` 一次拿整张,N 次锁 → 1 次 |
| I7 | chart 切分钟模式仍拉 K 线 | `loadChart` 只拉当前 tab 需要的图 |
| I8 | 板块聚合每 3s 全量重算 limit_flag | `QuoteCache` 写入 quote 时算 `limit_flag`,aggregator 直接读 |
| I9 | `/api/sectors/metrics` 每次返全字段 | 加 `?summary=1` query,只返 change_pct/turnover/stock_count |
| I10 | `get_stock_names()` 50 次全表扫 | 提到 `recompute()` 入口一次,传给 `_compute_sector` |

### 未修(本地单用户不适用)

| 编号 | 问题 | 说明 |
|------|------|------|
| C4 | 零认证 / 零授权 | 本地单用户,无对外服务 |
| C5 | 笔记 Markdown XSS | 自产笔记,无外部内容输入 |
| C6 | 无 CSRF | 本地单用户,无跨域攻击面 |

公网部署时需一并修这三项。

## 2026-07-07 前端稳定性修复

笔记下拉消失 + 日 K 首次不显示的根因和修法。

### 笔记下拉"消失"

| 根因 | 修法 |
|------|------|
| `selectStock` 找股用 `state.currentStocks`,但 `loadSectorStocks` 只把父板块直接股塞进去,子板块股不在 → 1113 行 `if (!stock) return` 提前返回,note-row 永不显示 | `loadSectorStocks` 在 `await Promise.all(loadSubSectorContent)` 之后,把子板块股合并进 `state.currentStocks`(Set 去重,父板块优先);另存 `state.currentDirectStocks` 给 `renderStockList` 用,避免重复渲染 |
| `bindDirectStockDrag` 每次 `renderStockList` 重渲都 `addEventListener('click', ...)`,N 次重渲 → 1 次点击 → N 次 `ui.selectStock`,多次"折叠旧 note-row"互相打架,看起来"消失" | 容器幂等标记 `container._dragBound`,只绑一次 |

### 日 K 首次"无数据"

| 根因 | 修法 |
|------|------|
| `selectStock` 走 `loadChart` 时,`needKline = state.chartMode === 'kline' && ...`,而 `chartMode` 默认 `'minute'`,所以**首次选股 K 线数据从不拉**。用户切到日 K tab → `renderKlineChart` 读 `state.chartData.kline` 是 `null` → "无数据" | `ui.switchChart` 改为 `async`,切到 kline 时若 `chartData.kline === null`,先 `await api(/kline)` 拉数据再渲染 |
