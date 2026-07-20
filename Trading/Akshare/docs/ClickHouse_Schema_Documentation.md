# 📊 ClickHouse 股票数仓架构文档 (Stock Data Warehouse)

**最后更新日期**: 2026-01-27  
**数据库名称**: `stock_data`  
**当前状态**: 纯净版 v3 架构 (100% 同步 Baostock)  
**对象统计**: 16 个生效对象 (12个表, 4个视图)

---

## 🚀 核心设计原则 (Design Principles)

1.  **存储事实 (Fact Storage)**: 涨跌停价格 (`limit_up/down`) 在载入时通过 Python 精确计算并固化存储。不再依赖数据库运行时物化，确保了回测环境与生产逻辑的 100% 一致。
2.  **幂等维护**: 采用 `ReplacingMergeTree` 引擎。通过 `update_time` 或 `snapshot_time` 机制，支持增量补齐和错误重跑。
3.  **极速检索**: 数据物理存储按 `(code, date)` 或相关主键排序，支持毫秒级的历史序列检索。

---

## 🔌 数据库连接说明 (Connection Reference)

系统通过 ClickHouse 的 HTTP 接口进行通信。连接配置统一定义在根目录的 `config.toml` 文件中。

### 1. 基础连接参数
*   **Host**: `127.0.0.1` (或 Docker 宿主机 IP)
*   **Port**: `8123` (HTTP 默认端口)
*   **User/Password**: `admin` / `admin_password`
*   **Default Database**: `stock_data`

---

## 📈 1. 行情事实层 (Market Fact Layer)

### 1.1 `stock_kline_day` - 个股日线表
存储全量 A 股历史记录（2021-01-01 至今）。

| 字段名 | 类型 | 说明 | 业务逻辑 |
| :--- | :--- | :--- | :--- |
| `code` | `LowCardinality(String)` | 证券代码 | 格式如 `sh.600000` |
| `date` | `Date` | 交易日期 | |
| `open` | `Float32` | 开盘价 | 不复权原生价格 |
| `high` | `Float32` | 最高价 | 不复权原生价格 |
| `low` | `Float32` | 最低价 | 不复权原生价格 |
| `close` | `Float32` | 收盘价 | 不复权原生价格 |
| `preclose` | `Float32` | 昨收价 | 前一交易日收盘价 |
| `volume` | `UInt64` | 成交量 | 单位：股 |
| `amount` | `Float64` | 成交额 | 单位：元 |
| `turn` | `Float32` | 换手率 | 百分比 (e.g. 5.5 = 5.5%) |
| `pctChg` | `Float32` | 涨跌幅 | 百分比 (e.g. 10.0 = 10%) |
| `tradestatus`| `UInt8` | 交易状态 | 1:正常, 0:停牌 |
| `isST` | `UInt8` | 是否ST | 1:是, 0:否 |
| `adjustflag` | `UInt8` | 复权类型 | 固定为 3 (不复权) |
| **`limit_up_price`** | `Float32` | **涨停价** | 基于规则计算的精确值 |
| **`limit_down_price`**| `Float32` | **跌停价** | 基于规则计算的精确值 |
| `limit_status` | `UInt8` | 涨跌停状态 | 1:涨停, 2:跌停, 3:炸板, 0:其他 |
| `update_time` | `DateTime` | 更新时间 | 用于 ReplacingMergeTree 版本控制 |

### 1.2 `index_kline_day` - 指数日线表
存储主要宽基指数、行业指数及自定义指数。

| 字段名 | 类型 | 说明 | 业务逻辑 |
| :--- | :--- | :--- | :--- |
| `code` | `LowCardinality(String)` | 指数代码 | 格式如 `sh.000001` |
| `date` | `Date` | 交易日期 | |
| `open` | `Float32` | 开盘价 | |
| `high` | `Float32` | 最高价 | |
| `low` | `Float32` | 最低价 | |
| `close` | `Float32` | 收盘价 | |
| `preclose` | `Float32` | 昨收 | |
| `volume` | `UInt64` | 成交量 | 单位：股/手 |
| `amount` | `Float64` | 成交额 | 单位：元 |
| `pctChg` | `Float32` | 涨跌幅 | 百分比 |
| `update_time` | `DateTime` | 更新时间 | |

### 1.3 `stock_snapshot_intraday` - 全市场实时快照表
存储盘中高频（~10s级）全市场快照，替代原有的 CSV 文件存储方案。

**存储策略**: 仅保留当日（或最近一次运行）数据。

| 字段名 | 类型 | 说明 | 业务逻辑与单位 |
| :--- | :--- | :--- | :--- |
| **`code`** | `LowCardinality(String)` | 证券代码 | 格式统一为 `sh.600000` |
| **`name`** | `LowCardinality(String)` | 证券简称 | 冗余存储，便于调试与人眼阅读 |
| **`snapshot_time`** | `DateTime` | **批次逻辑时间** | 发起这一轮全市场抓取的时间锚点 (Group Key) |
| **`source_time`** | `DateTime64(3)` | **数据源时间** | 接口返回的时间戳 |
| `price` | `Float32` | 最新成交价 | |
| `open` | `Float32` | 今日开盘价 | |
| `high` | `Float32` | 今日最高价 | |
| `low` | `Float32` | 今日最低价 | |
| `last_close` | `Float32` | 昨日收盘价 | |
| `change` | `Float32` | 涨跌额 | |
| `pct_chg` | `Float32` | 涨跌幅 | 单位：% (e.g. 1.5 = 1.5%) |
| **`volume`** | `UInt64` | **成交量 (股)** | |
| **`amount`** | `Float64` | **成交额 (元)** | |
| `turnover_rate` | `Float32` | 换手率 | |
| `total_market_cap`| `Float64` | 总市值 | |
| `float_market_cap`| `Float64` | 流通市值 | |
| `is_suspended` | `UInt8` | 是否停牌 | |

### 1.4 `concept_snapshot_intraday` - 板块指数实时快照表
存储盘中板块指数的实时行情快照。

| 字段名 | 类型 | 说明 | 业务逻辑 |
| :--- | :--- | :--- | :--- |
| `concept_name` | `LowCardinality(String)` | 板块名称 | |
| `date` | `Date` | 交易日期 | |
| `snapshot_time` | `DateTime` | 快照时间 | |
| `price_index` | `Float64` | 板块指数价格 | |
| `pct_chg` | `Float32` | 涨跌幅 | 百分比 |
| `change` | `Float32` | 涨跌额 | |
| `volume` | `Float64` | 成交量 | |
| `amount` | `Float64` | 成交额 | |
| `turnover_rate` | `Float32` | 换手率 | |
| `rise_count` | `UInt32` | 上涨家数 | |
| `fall_count` | `UInt32` | 下跌家数 | |
| `flat_count` | `UInt32` | 平盘家数 | |
| `limit_up_count` | `UInt32` | 涨停家数 | |
| `limit_down_count`| `UInt32` | 跌停家数 | |
| `suspended_count` | `UInt32` | 停牌家数 | |
| `stock_count` | `UInt32` | 成分股总数 | |
| `open` | `Float64` | 开盘点位 | |
| `high` | `Float64` | 最高点位 | |
| `low` | `Float64` | 最低点位 | |
| `last_close` | `Float64` | 昨收点位 | |

---

## 🏷️ 2. 板块与主题层 (Concept & Topic Layer)

### 2.1 `finance_concept_main` - 概念板块主表
记录概念板块的基础信息及其来源。

| 字段名 | 类型 | 说明 | 业务逻辑 |
| :--- | :--- | :--- | :--- |
| `name` | `LowCardinality(String)` | 概念名称 | |
| `source` | `LowCardinality(String)` | 来源 | 如 'eastmoney', 'sina' 等 |
| `update_time` | `DateTime` | 更新时间 | |

### 2.2 `finance_concept_components` - 概念成分股关联表
记录概念板块包含的个股。

| 字段名 | 类型 | 说明 | 业务逻辑 |
| :--- | :--- | :--- | :--- |
| `concept_name` | `LowCardinality(String)` | 概念名称 | |
| `stock_code` | `LowCardinality(String)` | 证券代码 | |
| `update_time` | `DateTime` | 更新时间 | |

### 2.3 `analysis_hot_topic_mapping` - 热门概念分析表
存储 AI 或分析逻辑生成的个股与热门概念的关联及理由。

| 字段名 | 类型 | 说明 | 业务逻辑 |
| :--- | :--- | :--- | :--- |
| `concept_name` | `LowCardinality(String)` | 概念名称 | |
| `stock_code` | `String` | 证券代码 | |
| `stock_name` | `String` | 证券名称 | |
| `reason` | `String` | 关联理由 | AI 生成的分析理由 |
| `update_time` | `DateTime` | 更新时间 | |

### 2.4 `view_selected_concept_list` - 优选概念视图
**核心功能**: 筛选成分股数量 <= 300 的概念板块，用于过滤过于宽泛的概念。

| 字段名 | 类型 | 说明 | 业务逻辑 |
| :--- | :--- | :--- | :--- |
| `concept_name` | `LowCardinality(String)` | 概念名称 | 仅包含成分股数量少于等于300的板块 |

### 2.5 `view_concept_components_filtered` - 优选概念成分视图
**核心功能**: 基于 `view_selected_concept_list` 过滤后的概念成分股清单。

| 字段名 | 类型 | 说明 | 业务逻辑 |
| :--- | :--- | :--- | :--- |
| `concept_name` | `LowCardinality(String)` | 概念名称 | |
| `stock_code` | `LowCardinality(String)` | 证券代码 | |
| `update_time` | `DateTime` | 更新时间 | |

---

## 🏛️ 3. 基础元数据层 (Metadata Layer)

### 3.1 `trade_calendar` - 交易日历表
解决 A 股非交易日空洞，是驱动回测引擎日期步进的核心。

| 字段名 | 类型 | 说明 | 业务逻辑 |
| :--- | :--- | :--- | :--- |
| `exchange` | `LowCardinality(String)` | 交易所代码 | 默认 `SSE` |
| `date` | `Date` | 日历日期 | |
| `is_trading_day`| `UInt8` | 是否交易日 | 1:是, 0:否 |
| `wday` | `UInt8` | 星期几 | 0=周一, 6=周日 |
| `prev_trading_date`| `Date` | 上一交易日 | 冗余存储，加速偏移查询 |
| `next_trading_date`| `Date` | 下一交易日 | 冗余存储，加速偏移查询 |

### 3.2 `securities_info` - 证券基础档案
记录所有曾上市及现存 A 股的基本属性。

| 字段名 | 类型 | 说明 | 业务逻辑 |
| :--- | :--- | :--- | :--- |
| `code` | `LowCardinality(String)` | 证券代码 | |
| `symbol` | `String` | 中文简称 | 如“中国平安” |
| `ipo_date` | `Date` | 上市日期 | 用于回测起始过滤 |
| `out_date` | `Date` | 退市日期 | 若未退市为 `2999-12-31` |
| `type` | `UInt8` | 资产类型 | 1:股票, 2:指数 |
| `update_time` | `DateTime` | 更新时间 | |
| `total_shares` | `Float64` | 总股本 | 单位：股（推测） |

### 3.3 `adjust_factor` - 复权因子表
| 字段名 | 类型 | 说明 | 业务逻辑 |
| :--- | :--- | :--- | :--- |
| `code` | `LowCardinality(String)` | 证券代码 | |
| `dividOperateDate`| `Date` | 除息除权日 | 分红落地日期 |
| `foreAdjustFactor`| `Float64` | 前复权因子 | 对应日期及其之前的价格乘数 |
| `backAdjustFactor`| `Float64` | 后复权因子 | 对应比例的累积连乘积 |
| `dt` | `DateTime` | 更新时间 | |

---

## 🧠 4. 策略分析视图 (Analytics Layer)

### 4.1 `strategy_flu_params` - 策略动态配置 (TinyLog)
| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `end_date` | `Date` | 策略扫描的基准日期 (T 日) |
| `upper_limit` | `Float64` | 回撤上限 (如 0.75 表示回撤 75% 空间) |
| `lower_limit` | `Float64` | 回撤下限 (如 0.0 表示不回撤) |

### 4.2 `view_strategy_flu` - 首板回调选股视图
**核心功能**: 实时自动化筛选“首板回调”形态。该模型寻找那些近期经历过涨停、随后出现良性回撤且未跌破安全区的个股。

**(详细逻辑请参考 SQL 定义或历史文档)**

| 字段名 | 类型 | 说明 | 业务逻辑 |
| :--- | :--- | :--- | :--- |
| `code` | `LowCardinality(String)` | 股票代码 | 符合条件的标的 |
| `limit_up_close_price` | `Float32` | 涨停日收盘价 | 回调计算的基准高点 |
| `high_after_limit` | `Float32` | 涨停后最高价 | 识别是否有二板或更强走势 |
| `low_after_limit` | `Float32` | 涨停后最低价 | 寻找回踩点 |
| `pre_limit_up_preclose`| `Float32` | 涨停前昨收价 | 用于计算涨停板的空间长度 |
| `high_drawdown` | `Float64` | 最高点回撤比 | (涨停收盘 - 之后最高) / 板长 |
| `low_drawdown` | `Float64` | 最低点回撤比 | (涨停收盘 - 之后最低) / 板长 |

### 4.3 `strategy_flu_stock_pool` - 策略特定票池 (TinyLog)
用于限制策略扫描范围的临时或固定股票池。

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `code` | `String` | 证券代码 |

### 4.4 `view_strategy_flu_pool` - 基于特定票池的首板回调视图
**核心功能**: 与 `view_strategy_flu` 逻辑一致，但仅对 `strategy_flu_stock_pool` 中的股票进行筛选。
适用于针对特定板块（如“自选股”或“概念板块”）进行快速回调扫描。

| 字段名 | 类型 | 说明 | 业务逻辑 |
| :--- | :--- | :--- | :--- |
| `code` | `LowCardinality(String)` | 股票代码 | 符合条件的标的 |
| `limit_up_close_price` | `Float32` | 涨停日收盘价 | |
| `high_after_limit` | `Float32` | 涨停后最高价 | |
| `low_after_limit` | `Float32` | 涨停后最低价 | |
| `pre_limit_up_preclose`| `Float32` | 涨停前昨收价 | |
| `high_drawdown` | `Float64` | 最高点回撤比 | |
| `low_drawdown` | `Float64` | 最低点回撤比 | |

---

## ⚙️ 5. 技术特性监控 (Technical Audit)

*   **数据量级**: 约 650 万行事实记录。
*   **物理架构**: 
    *   个股月分区 (`toYYYYMM`) 兼顾了查询性能与分块维护。
    *   全库启用 LZ4 压缩，大幅降低 IO 损耗。
*   **一致性保障**: `limit_status` 是数据质量的信任之源，所有回测逻辑必须基于此字段执行。

---
*文档生成于：2026-01-27 (Beijing Time)*
