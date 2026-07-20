# 股票数据库文档

## 数据库概述
本数据库存储股票市场数据，包含个股日K线数据、指数日K线数据，以及策略执行所需的参数和中间结果。
数据库名称为stock_data。

## 表结构说明

### 1. 个股日K线表 (daily_k)

#### 表结构
| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| code | LowCardinality(String) | - | 股票代码 |
| date | Date | - | 交易日 |
| open | Float32 | - | 开盘价 |
| high | Float32 | - | 最高价 |
| low | Float32 | - | 最低价 |
| close | Float32 | - | 收盘价 |
| preclose | Float32 | - | 前收盘价 |
| volume | UInt64 | - | 成交量(股) |
| amount | Float64 | - | 成交额(元) |
| turn | Float32 | - | 换手率(%) |
| tradestatus | UInt8 | 1 | 交易状态(1:正常 0:停牌) |
| isST | UInt8 | 0 | 是否ST股票(0:否 1:是) |
| adjustflag | String | - | 复权类型 |
| dt | DateTime | now() | 数据更新时间 |
| limit_range | Float32 | MATERIALIZED | 涨跌幅限制比例(自动计算) |
| upper_limit | Float32 | MATERIALIZED | 涨停价(自动计算) |
| lower_limit | Float32 | MATERIALIZED | 跌停价(自动计算) |
| price_status | UInt8 | MATERIALIZED | 当日走势状态(0:其他 1:涨停 2:跌停 3:触涨停未封 4:触跌停未封) |

#### 计算列逻辑
1. **limit_range** (涨跌幅限制比例):
   - 科创板(代码sh.688开头): 20%
   - 创业板(代码sz.300开头): 20%
   - ST股票: 5%
   - 其他: 10%

2. **upper_limit** (涨停价):  
   `round(preclose * (1 + limit_range), 2)`

3. **lower_limit** (跌停价):  
   `round(preclose * (1 - limit_range), 2)`

4. **price_status** (当日走势状态):
   - 1: 收盘价=涨停价(封涨停板收盘)
   - 2: 收盘价=跌停价(封跌停板收盘)
   - 3: 最高价≥涨停价 AND 收盘价<涨停价(触及涨停但未封板)
   - 4: 最低价≤跌停价 AND 收盘价>跌停价(触及跌停但未封板)
   - 0: 其他情况

---

### 2. 前复权个股日K线表 (daily_k_fore)

#### 表结构
| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| code | LowCardinality(String) | - | 股票代码 |
| date | Date | - | 交易日 |
| open | Float32 | - | 开盘价（前复权） |
| high | Float32 | - | 最高价（前复权） |
| low | Float32 | - | 最低价（前复权） |
| close | Float32 | - | 收盘价（前复权） |
| preclose | Float32 | - | 前收盘价（前复权） |
| volume | UInt64 | - | 成交量(股) |
| amount | Float64 | - | 成交额(元) |
| turn | Float32 | - | 换手率(%) |
| tradestatus | UInt8 | 1 | 交易状态(1:正常 0:停牌) |
| isST | UInt8 | 0 | 是否ST股票(0:否 1:是) |
| adjustflag | String | - | 复权类型（标记为"front"或"前复权"） |
| dt | DateTime | now() | 数据更新时间 |
| limit_range | Float32 | MATERIALIZED | 涨跌幅限制比例(自动计算)，基于复权后价格计算 |
| upper_limit | Float32 | MATERIALIZED | 涨停价(自动计算)，考虑ST股5%、普通股10%限制 |
| lower_limit | Float32 | MATERIALIZED | 跌停价(自动计算)，考虑ST股5%、普通股10%限制 |
| price_status | UInt8 | MATERIALIZED | 当日走势状态(0:其他 1:涨停 2:跌停 3:触涨停未封 4:触跌停未封) |

#### 计算列逻辑
1. **limit_range** (涨跌幅限制比例):
   - 科创板(代码688开头): 20%
   - 创业板(代码300开头): 20%
   - ST股票: 5%
   - 其他: 10%

2. **upper_limit** (涨停价):  
   `round(preclose * (1 + limit_range), 2)`

3. **lower_limit** (跌停价):  
   `round(preclose * (1 - limit_range), 2)`

4. **price_status** (当日走势状态):
   - 1: 收盘价=涨停价(封涨停板收盘)
   - 2: 收盘价=跌停价(封跌停板收盘)
   - 3: 最高价≥涨停价 AND 收盘价<涨停价(触及涨停但未封板)
   - 4: 最低价≤跌停价 AND 收盘价>跌停价(触及跌停但未封板)
   - 0: 其他情况

---

### 3. 指数日K线表 (index_k)

#### 表结构
| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| code | LowCardinality(String) | - | 指数代码 |
| date | Date | - | 交易日 |
| open | Float32 | - | 开盘指数 |
| high | Float32 | - | 最高指数 |
| low | Float32 | - | 最低指数 |
| close | Float32 | - | 收盘指数 |
| preclose | Float32 | - | 前收盘指数 |
| volume | UInt64 | - | 成交量 |
| turn | Float32 | - | 换手率(%) |
| tradestatus | UInt8 | 1 | 交易状态(1:正常 0:停牌) |
| dt | DateTime | now() | 数据更新时间 |

---

### 4. 首板回调策略参数表 (strategy_flu_params)

> 存储首板回调策略的动态参数，每次策略执行前由 Python 更新。

#### 表结构
| 字段名 | 类型 | 说明 |
|--------|------|------|
| end_date | Date | 策略执行的截止日期（T日候选） |
| upper_limit | Float64 | 回撤幅度上限（如 0.75 表示 75%） |
| lower_limit | Float64 | 回撤幅度下限（如 0.0 表示 0%） |

#### 存储引擎
- **ENGINE**: `TinyLog`
- **说明**: 数据极小（仅1行），无需索引或分区，轻量高效。

---

### 5. 首板回调策略股票池表 (strategy_flu_stock_pool)

> 存储首板回调策略的选股范围。空表表示全市场选股，有数据表示仅从该池中选股。

#### 表结构
| 字段名 | 类型 | 说明 |
|--------|------|------|
| code | String | 股票代码 |

#### 存储引擎
- **ENGINE**: `TinyLog`
- **说明**: 临时表，每次策略执行前清空并重写。

---

### 6. 首板回调策略视图 (view_strategy_flu)

> 全市场选股的策略结果视图。基于 `daily_k` 和 `strategy_flu_params` 计算，输出符合首板回调条件的股票。

#### 输出列
| 列名 | 说明 |
|------|------|
| code | 股票代码 |
| first_limit_close | 涨停封板价 |
| post_limit_max_price | 涨停后（L+1 至 T 日）的最高价（open/close 中的最高） |
| post_limit_min_price | 涨停后（L+1 至 T 日）的最低价（open/close 中的最低） |
| first_limit_preclose | 涨停前一日收盘价 |
| callback_from_max_percent | 从涨停封板价到板后最高价的回撤比例 |
| callback_from_min_percent | 从涨停封板价到板后最低价的回撤比例 |

#### 依赖
- `stock_data.daily_k`
- `stock_data.strategy_flu_params`

---

### 7. 首板回调策略股票池视图 (view_strategy_flu_pool)

> 从指定股票池中选股的策略结果视图。逻辑与 `view_strategy_flu` 相同，但增加对 `strategy_flu_stock_pool` 的过滤。

#### 输出列
与 `view_strategy_flu` 相同。

#### 依赖
- `stock_data.daily_k`
- `stock_data.strategy_flu_params`
- `stock_data.strategy_flu_stock_pool`

---

## 数据库技术细节
- **存储引擎**: 
  - `daily_k`, `index_k`: `ReplacingMergeTree`
  - `strategy_flu_params`, `strategy_flu_stock_pool`: `TinyLog`
- **排序键**: 
  - `daily_k`, `index_k`: `(code, date)`
- **分区策略**: 
  - `daily_k`, `index_k`: 按年分区 (`toYear(date)`)
- **索引粒度**: 1024