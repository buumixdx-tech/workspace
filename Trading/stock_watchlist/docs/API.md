# Watchlist API 文档

## 概览

Base URL: `http://127.0.0.1:5181/api`

所有接口统一返回 JSON，结构如下：

```json
{ "ok": true, "data": {...} }
{ "ok": false, "error": "错误描述" }
```

错误响应 HTTP 状态码为 4xx 或 500。

---

## 健康检查

### `GET /api/health`

检查服务状态和 TdxClient 连通性。

```json
{ "ok": true, "tdx": "ready" }
{ "ok": false, "tdx": "connection error message", "error": "..." }
```

---

## 板块（Sectors）

### 板块树

#### `GET /api/sectors`

返回完整板块树（嵌套 children），不含股票。每节点内嵌实时聚合指标。

**响应字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 板块 ID |
| `name` | string | 板块名称 |
| `parent_id` | int \| null | 父板块 ID |
| `sort_order` | int | 排序值 |
| `color` | string | 颜色 HEX |
| `children` | array | 子板块数组 |
| `change_pct` | float \| null | 涨跌幅（小数，如 0.0123 = +1.23%） |
| `turnover` | float \| null | 换手率（小数，如 0.05 = 5%） |

---

### 聚合指标

#### `GET /api/sectors/metrics`

返回所有板块的实时聚合指标。

**响应：** `{ sector_id: { change_pct, turnover, top_gainers, top_losers, contributors, stock_count, ts } }`

| 字段 | 类型 | 说明 |
|------|------|------|
| `change_pct` | float \| null | 加权涨跌幅 |
| `turnover` | float \| null | 换手率 |
| `top_gainers` | array | 涨幅前N（见下） |
| `top_losers` | array | 跌幅前N |
| `contributors` | array | 贡献排名（change_pct × 权重） |
| `stock_count` | int | 股票数量 |
| `ts` | float | 时间戳 |

`top_gainers / top_losers / contributors` 每条记录：
```json
{ "code": "sh.600519", "name": "贵州茅台", "change_pct": 0.023, "limit_flag": "up"|"down"|null }
```

#### `GET /api/sectors/metrics/config`

读取当前聚合配置。

```json
{ "ok": true, "data": { "weight_mode": "total", "top_n": 3, "period": "today" } }
```

| 字段 | 可选值 | 说明 |
|------|--------|------|
| `weight_mode` | `total` / `circulating` / `equal` | 加权方式：总市值 / 流通市值 / 等权 |
| `top_n` | 1-20 | top 涨跌幅显示数量 |
| `period` | `today` | 统计周期 |

#### `PUT /api/sectors/metrics/config`

更新聚合配置。立即触发重算。

**Body：**
```json
{ "weight_mode": "circulating", "top_n": 5 }
```
所有字段可选，只更新提供的字段。

#### `GET /api/sectors/metrics/filter`

读取当前 label 过滤集合。`null` 表示不过滤（显示全部）。

```json
{ "ok": true, "data": { "labels": ["core", "focus", "monitor", "observation"] } }
```

#### `PUT /api/sectors/metrics/filter`

设置 label 过滤，控制聚合指标只计算哪些 label 的股票。

**Body：**
```json
{ "labels": ["core", "focus"] }
```
传入 `null` 清除过滤（显示全部）。

`monitor` 和 `observation` 互通（后端自动合并）。

---

### 单板块详情

#### `GET /api/sectors/:sector_id`

```json
{ "ok": true, "data": { "id": 101, "name": "PCB", ..., "stocks": [...] } }
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `include_stocks` | query | `true` = 递归聚合所有子孙板块股票；默认 `false` 只返回直接关联股票 |

---

#### `GET /api/sectors/:sector_id/tree`

返回板块的直接个股 + 直接子板块摘要，用于前端渲染。

```json
{
  "ok": true,
  "data": {
    "sector": { "id": 101, "name": "PCB", "metrics": {...} },
    "stocks": [{ "stock_code": "...", "name": "...", "label": "core", ... }],
    "children": [
      { "id": 109, "name": "PCB钻针", "color": "#ff0000",
        "core_focus_count": 3, "change_pct": 0.01, "turnover": 0.04 }
    ]
  }
}
```

---

### 板块 CRUD

#### `POST /api/sectors`

创建板块。

**Body：**
```json
{ "name": "半导体零件", "parent_id": 118, "color": "#6b7280", "sort_order": 0 }
```
`parent_id` 可省略（创建顶级板块）。`color` 默认 `#6b7280`。`sort_order` 默认 0。

#### `PUT /api/sectors/:sector_id`

更新板块字段。

**Body（所有字段可选）：**
```json
{ "name": "新名称", "parent_id": 102, "sort_order": 2048, "color": "#ff0000" }
```

`parent_id` 变更自动同步 `sector_relations` 表。

#### `DELETE /api/sectors/:sector_id`

删除板块（含所有子板块）。股票不会被删除，只解除关联。

---

### 诊断

#### `GET /api/sectors/:sector_id/cache_coverage`

**诊断端点** — 检查板块（含所有子板块的 descendant）的每只股票在 QuoteCache / ProfileCache 里的命中情况。

用于排查 `contributors` 数量异常（如板块有 N 只股票但 contributors < 3）。

**响应字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `total` | int | 板块内总股票数（含子板块） |
| `with_quote` | int | 有 quote cache 的股数 |
| `with_profile` | int | 有 profile cache 的股数 |
| `with_profile_mv` | int | profile 含 `total_market_value` 的股数 |
| `stocks.{code}.quote` | bool | 该股 quote cache 是否命中 |
| `stocks.{code}.profile` | bool | 该股 profile cache 是否命中 |
| `stocks.{code}.profile_mv` | bool | profile 是否含市值字段 |

```json
{
  "ok": true,
  "data": {
    "total": 25, "with_quote": 25, "with_profile": 23, "with_profile_mv": 23,
    "stocks": { "sh.600519": { "quote": true, "profile": true, "profile_mv": true }, ... }
  }
}
```

---

## 板块-个股关联（Sector Stocks）

### 列表

#### `GET /api/sectors/:sector_id/stocks`

返回该板块直接关联的全部股票（含实时行情）。

每条记录包含 `stock_code`、`name`、`label`、`sort_order` 及实时 `quote`。

---

### 添加

#### `POST /api/sectors/:sector_id/stocks`

添加股票到板块（可自动录入股票信息）。

**Body：**
```json
{ "stock_code": "sh.600519", "label": "core" }
```

| 字段 | 必须 | 说明 |
|------|------|------|
| `stock_code` | 是 | 股票代码 |
| `label` | 否 | 标注类型，默认 `observation` |

`label` 可选值：`core` / `focus` / `monitor` / `associate`

A股股票自动补全信息（名称、板块等）。港美股自动转为 YF 格式存储。

返回插入/更新后的关联记录。

---

#### `POST /api/sectors/:sector_id/stocks/batch`

批量添加多只股票到同一板块。

**Body：**
```json
{
  "stocks": [
    { "stock_code": "sh.600519", "label": "core" },
    { "stock_code": "sh.000858", "label": "focus" }
  ]
}
```

返回添加后该板块全部关联记录及数量。

---

### 更新

#### `PUT /api/sectors/:sector_id/stocks/:code`

更新个股在板块中的属性（目前支持 `label` 和 `sort_order`）。

**Body（所有字段可选）：**
```json
{ "label": "focus", "sort_order": 1024 }
```

`label` 可选值：`core` / `focus` / `monitor` / `associate`

---

### 排序

#### `PUT /api/sectors/:sector_id/stocks/reorder`

批量更新板块内个股顺序。

**Body：**
```json
{ "codes": ["sh.600519", "sh.000858", "sz.000001"] }
```
传入期望的完整顺序列表，`sort_order` 自动按 0, 1024, 2048... 分配。

---

### 移除

#### `DELETE /api/sectors/:sector_id/stocks/:code`

将股票从板块移除（解除关联，股票本身不删除）。

---

### 移动

#### `PUT /api/stocks/:code/sectors`

将股票从源板块移到目标板块。

**Body：**
```json
{ "from_sector_id": 101, "to_sector_id": 102, "label": "focus" }
```

| 字段 | 必须 | 说明 |
|------|------|------|
| `from_sector_id` | 是 | 源板块 ID |
| `to_sector_id` | 是 | 目标板块 ID |
| `label` | 否 | 目标板块中的标注类型，默认 `observation` |

如果目标板块中已有该股票，则更新 label；如果没有，则创建关联。

---

## 股票（Stocks）

### 搜索

#### `GET /api/stocks/search`

搜索股票。

| 参数 | 类型 | 说明 |
|------|------|------|
| `q` | query | 搜索词（代码或名称） |
| `limit` | query | 返回数量上限，默认 20，最大 100 |

港美股代码（以 `.HK` 结尾或全大写）直接查 Yahoo Finance；A 股查本地缓存。

**响应字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `query` | string | 回显查询词 |
| `count` | int | 命中条数 |
| `data[].code` | string | 代码（YF 格式，如 `00700.HK` 或 `AAPL`） |
| `data[].name` | string | 股票名称 |
| `data[].board_name` | string | 板块/货币 |

---

### 列表

#### `GET /api/stocks`

返回系统全部股票（stocks 表，不含实时行情）。

**响应字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `count` | int | 总数 |
| `data[].code` | string | 代码（内部 CK 格式，如 `sh.600519`） |
| `data[].name` | string | 股票名称 |
| `data[].exchange` | string | 交易所（`sh`/`sz`/`bj`/`HK`/`US`） |
| `data[].board` | string | 板块代码 |
| `data[].board_name` | string | 板块名称 |

```json
{ "ok": true, "data": [...], "count": 399 }
```

---

### 添加到自选

#### `POST /api/stocks`

添加股票到自选股列表（不入板块）。

支持 form 表单（`code`）或 JSON body（`code`）。

A 股走 eltdx 补全；港美股转为 YF 格式存储。

**响应：** 201 Created，返回添加的 stock 记录。

---

### 个股详情

#### `GET /api/stocks/:code`

返回股票详细信息 + 实时行情。

A 股优先从 QuoteCache（3s 刷新）读，Cache Miss 时回写；港美股走 Yahoo Finance。

```json
{
  "ok": true,
  "data": {
    "code": "sh.600519",
    "name": "贵州茅台",
    "board_name": "白酒",
    "quote": {
      "last_price": 1680.00,
      "change": 23.50,
      "change_pct": 0.0142,
      "turnover_rate": 0.0032,
      ...
    }
  }
}
```

---

### 所属板块

#### `GET /api/stocks/:code/sectors`

返回该股票所属的全部板块。

```json
{ "ok": true, "data": [{ "id": 101, "name": "消费", ... }], "count": 2 }
```

---

### 批量 quote（C7 性能优化）

#### `GET /api/stocks/quotes?codes=a,b,c`

一次 HTTP 拿 N 只股票的 quote。供前端 3s tick 批量轮询用（替代 N 次单只请求）。

**Query 参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `codes` | string | 逗号分隔的股票代码，最多 200 只 |

**数据源（全部走内存缓存，无网络调用）：**
- A 股：`QuoteCache`（daemon 3s tick 维护）
- 港美股：`YfCache`（daemon 30s tick 维护）
- miss 返回 `null`，前端用 stale 数据兜底

**响应：**

```json
{
  "ok": true,
  "data": {
    "sh.600519": { "last_price": 1680.0, "change": 23.5, "change_pct": 0.0142, "limit_flag": null, ... },
    "sz.000001": { "last_price": 12.5, "change": 0.05, ... },
    "00700.HK": null
  }
}
```

**错误：**
- 400 `codes 必填,逗号分隔` / `一次最多 200 只`

---

### 分时

#### `GET /api/stocks/:code/minute`

当日分时数据。

A 股返回 1m bar（补了 9:30 和 15:00 占位 bar）；港美股返回 5m bar。

```json
{
  "ok": true,
  "data": {
    "code": "sh.600519",
    "exchange": "sh",
    "prev_close": 1656.50,
    "points": [
      { "time_label": "09:30", "price": 1658.00, "avg_price": 1658.00, "volume": 0 },
      { "time_label": "09:31", "price": 1660.00, "avg_price": 1659.20, "volume": 12345 },
      ...
    ]
  }
}
```

---

### K 线

#### `GET /api/stocks/:code/kline`

K 线数据。

| 参数 | 类型 | 说明 |
|------|------|------|
| `period` | query | 周期：`day`(日线) / `week`(周线) / `month`(月线)，默认 `day` |
| `count` | query | 根数，默认 300，最大 1000 |
| `adjust` | query | 复权：`qfq` / `hfq` / `none`，默认 `qfq` |

A 股走 eltdx；港美股走 Yahoo Finance。

```json
{
  "ok": true,
  "data": {
    "code": "sh.600519",
    "exchange": "sh",
    "period": "day",
    "bars": [
      { "time": "2026-06-27T15:00:00", "open": 1660.0, "high": 1685.0,
        "low": 1655.0, "close": 1680.0, "volume": 1234567, "amount": 2067890000.0 },
      ...
    ],
    "limit_up": 1818.00,
    "limit_down": 1521.00,
    "pre_close": 1656.50
  }
}
```

---

## 笔记（Notes）

### 列表

#### `GET /api/stocks/:code/notes`

返回该股票的全部笔记（按更新时间倒序）。

```json
{
  "ok": true,
  "data": [
    {
      "id": 1,
      "stock_code": "sh.600519",
      "title": "Q2业绩",
      "body": "营收同比增长15%...",
      "tags": ["业绩", "白酒"],
      "created_at": "2026-07-01T10:00:00",
      "updated_at": "2026-07-02T14:30:00"
    }
  ]
}
```

---

### 创建

#### `POST /api/stocks/:code/notes`

为股票创建笔记。股票必须已存在于系统中。

**Body：**
```json
{ "title": "Q2业绩", "body": "营收同比增长15%...", "tags": ["业绩"] }
```
`title` 最多 15 字，`body` 最多 300 字，`tags` 为字符串数组（最多 10 个）。超限返 400。

---

### 详情

#### `GET /api/notes/:note_id`

返回指定笔记详情。

---

### 更新

#### `PUT /api/notes/:note_id`

更新笔记内容。

**Body：**
```json
{ "title": "新标题", "body": "新内容", "tags": ["新标签"] }
```
只更新提供的字段。

---

### 删除

#### `DELETE /api/notes/:note_id`

删除指定笔记。

---

### 批量操作

#### `DELETE /api/stocks/:code/notes`

删除该股票的全部笔记。返回删除数量。

```json
{ "ok": true, "deleted": 5 }
```

#### `PUT /api/notes/:note_id/move`

将笔记迁移到另一股票。

**Body：**
```json
{ "stock_code": "sh.600519" }
```
目标股票必须已存在于系统中。

---

## Label 标注体系

每只股票在每个板块中有一个 label 标注：

| label | 名称 | 说明 |
|-------|------|------|
| `core` | 核心 | 最重要标的 |
| `focus` | 关注 | 重点关注 |
| `monitor` | 观察 | 观察标的（兼容旧数据 `observation`） |
| `associate` | 关联 | 关联标的 |

`monitor` 和 `observation` 在系统中互通（后端和前端透明处理）。

---

## 聚合指标说明

板块聚合指标（涨跌幅、换手率）默认计算该板块**所有 label 的股票**，可通过 `PUT /api/sectors/metrics/filter` 过滤到特定 label 范围。

权重模式：
- `total` — 按总市值加权（默认）
- `circulating` — 按流通市值加权
- `equal` — 等权

非交易日（全部价格未变）：`change_pct` 和 `turnover` 返回 `null`。

---

## 指数快照（topbar 用）

#### `GET /api/indices`

返回 6 个固定指数的最新 quote — 前端 topbar **3s tick 拉一次**，6 列横排。

**固定顺序：** 上证 → 深成 → 科创 → 日经225 → 韩国 KOSPI → 台湾加权

**响应：**

```json
{
  "ok": true,
  "data": [
    {
      "key": "sh000001",
      "name": "上证",
      "src": "eltdx",
      "quote": {
        "last_price": 3254.18,
        "change": 12.45,
        "change_pct": 0.00384,
        "open": 3241.73,
        "high": 3268.50,
        "low": 3238.10,
        "pre_close": 3241.73
      }
    },
    { "key": "sz399001", "name": "深成", "src": "eltdx", "quote": { ... } },
    { "key": "sh000688", "name": "科创", "src": "eltdx", "quote": { ... } },
    { "key": "^N225",    "name": "日经225",  "src": "yf", "quote": { ... } },
    { "key": "^KS11",    "name": "韩国 KOSPI", "src": "yf", "quote": { ... } },
    { "key": "^TWII",    "name": "台湾加权",  "src": "yf", "quote": { ... } }
  ]
}
```

**数据源：**
- A 股 3 个（上证 / 深成 / 科创）走 eltdx 批量
- 海外 3 个（日经225 / 韩国 KOSPI / 台湾加权）走 yfinance spark 批量

**刷新策略：** 3s tick（与 `QuoteCache` 同节奏），后台双源并行拉取，任一源失败不影响另一源。

**冷启动行为：** daemon 启动时同步首次拉取，前端首屏不会拿到空数据。运行中某源失败进 60s cooldown，期间该指数 `quote` 为 `null`，UI 显示 `--`。

**quote 字段缺值语义：** `last_price` / `change` / `change_pct` 任一为 `null` 时前端显示 `--`，不参与涨跌色计算。

---

## 管理端点（本地单用户）

### 强制重算

#### `POST /api/admin/recompute`

强制 daemon 失效 A 股 cache 池子 + 立即重算 SectorAggregator。

**用途：** `import_xlsx.py` 等离线脚本灌库完成后调用 — 否则前端 metrics 要等 30s TTL 过期才刷新。本地单用户场景，无认证、无 CSRF。

**响应：**

```json
{ "ok": true }
```

---

## 错误响应

**所有端点都被 `@_safe` 装饰器包裹**。它捕获两类异常：

1. **`src.errors.ApiError` 子类** — 业务校验错误，按 `status` 返对应 HTTP 码
   - `BadRequest` → 400
   - `NotFound` → 404
   - `Conflict` → 409
   - `Unauthorized` → 401（预留）
   - `Forbidden` → 403（预留）
2. **其他 `Exception`** → 500 兜底

成功响应：

```json
{ "ok": true, "data": {...} }
```

业务错误响应（`ApiError` 子类）：

```json
{ "ok": false, "error": "stock_code 必填" }
```

500 兜底响应：

```json
{ "ok": false, "error": "ValueError: invalid literal for int() with base 10: 'abc'" }
```

HTTP 状态码总览：

| 状态码 | 触发条件 | 备注 |
|--------|---------|------|
| **200** | 成功 | 默认 |
| **201** | 成功创建（POST） | `POST /api/sectors`、`POST /api/sectors/:id/stocks`、`POST /api/stocks`、`POST /api/stocks/:code/notes` |
| **400** | `BadRequest` 抛出 | 字段缺失、格式错、长度超限、值非法（label / codes / ids） |
| **404** | `NotFound` 抛出 | 板块不存在、关联不存在、笔记不存在、股票不在自选 |
| **500** | `@_safe` 兜底所有未捕获异常 | 真服务端 bug,客户端应上报 |
| **503** | `/api/health` TdxClient 不可用 | |

⚠️ **客户端注意**：`error` 字段是开发者面向的描述，500 时**带异常类名**（不要展示给终端用户）。HTTP 码现在可靠 —— 4xx 是客户端错，5xx 是服务端错，可直接按状态码分支处理。

---

## 已知问题

### 2026-07-07 审查 → 2026-07-07 全部修完

详细修复日志见 [`README.md` 修复日志](../README.md#2026-07-07-修复日志)。16 条本地相关问题全部修完：

- **正确性**：C1 / C2 / C3 / I4 / I5 / I11
- **性能**：C7 / C8 / I2 / I3 / I6 / I7 / I8 / I9 / I10

### 公网部署前必修（本地不适用）

| # | 问题 | 公网要求 |
|---|------|---------|
| C4 | 零认证 / 零授权 | session + `@login_required` |
| C5 | 笔记 Markdown XSS（`renderMd` innerHTML 无转义） | DOMPurify 净化 |
| C6 | 无 CSRF token | token 或 Origin 白名单 + SameSite=Strict cookie |

这三项触发条件是"对外部用户暴露 HTTP 端口"，本地单用户跑不触发。如果未来上公网/局域网多人，必须一并修。
