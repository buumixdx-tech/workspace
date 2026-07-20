-- ============================================================
-- ClickHouse Schema Design v3 (Final)
-- 策略：ETL负责计算，DB负责存储 (Store Facts, Not Logic)
-- ============================================================

CREATE DATABASE IF NOT EXISTS stock_data;

-- ------------------------------------------------------------
-- 1. [核心] A股个股日线行情表 (stock_kline_day)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_data.stock_kline_day
(
    -- 维度
    `code` LowCardinality(String) COMMENT '证券代码 (e.g. sh.600000)',
    `date` Date COMMENT '交易日期',
    
    -- 基础行情
    `open` Float32,
    `high` Float32,
    `low` Float32,
    `close` Float32,
    `preclose` Float32 COMMENT '前收盘价',
    `volume` UInt64 COMMENT '成交量(股)',
    `amount` Float64 COMMENT '成交额(元)',
    
    -- 衍生指标
    `turn` Float32 COMMENT '换手率(%)',
    `pctChg` Float32 COMMENT '涨跌幅(%)',
    
    -- 状态标志 (ETL清洗后)
    `tradestatus` UInt8 DEFAULT 1 COMMENT '交易状态(1:正常 0:停牌)',
    `isST` UInt8 DEFAULT 0 COMMENT '是否ST(0:否 1:是)',
    `adjustflag` UInt8 DEFAULT 3 COMMENT '复权类型(3:不复权)',
    
    -- [关键变更] 显式存储涨跌停价格 (由Python ETL计算精确值存入)
    -- 即使是历史数据，这些值也是确定的事实。
    `limit_up_price` Float32 COMMENT '涨停价(精确到分)',
    `limit_down_price` Float32 COMMENT '跌停价(精确到分)',
    
    -- 封板状态 (可选，也可以回测时实时算，但存下来查询更快)
    -- 0:无 1:涨停 2:跌停 3:炸板
    `limit_status` UInt8 DEFAULT 0,

    `update_time` DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(update_time)
PARTITION BY toYYYYMM(date)
ORDER BY (code, date)
SETTINGS index_granularity = 8192;

-- ------------------------------------------------------------
-- 2. 指数日线行情表 (index_kline_day)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_data.index_kline_day
(
    `code` LowCardinality(String),
    `date` Date,
    `open` Float32,
    `high` Float32,
    `low` Float32,
    `close` Float32,
    `preclose` Float32,
    `volume` UInt64,
    `amount` Float64,
    `pctChg` Float32,
    `update_time` DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(update_time)
PARTITION BY toYear(date)
ORDER BY (code, date);

-- ------------------------------------------------------------
-- 3. 交易日历表 (trade_calendar)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_data.trade_calendar
(
    `exchange` LowCardinality(String) DEFAULT 'SSE',
    `date` Date,
    `is_trading_day` UInt8 COMMENT '1=是, 0=否',
    `wday` UInt8 COMMENT '0=周一...6=周日',
    `prev_trading_date` Date,
    `next_trading_date` Date
)
ENGINE = ReplacingMergeTree()
ORDER BY (exchange, date);

-- ------------------------------------------------------------
-- 4. 证券基础信息表 (securities_info)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_data.securities_info
(
    `code` LowCardinality(String),
    `symbol` String COMMENT '中文简称',
    `ipo_date` Date COMMENT '上市日期',
    `out_date` Date COMMENT '退市日期(或2999-12-31)',
    `type` UInt8 COMMENT '1=股票, 2=指数',
    `update_time` DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(update_time)
ORDER BY code;

-- ------------------------------------------------------------
-- 5. 复权因子表 (adjust_factor)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_data.adjust_factor
(
    `code` LowCardinality(String),
    `dividOperateDate` Date,
    `foreAdjustFactor` Float64,
    `backAdjustFactor` Float64,
    `update_time` DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(update_time)
ORDER BY (code, dividOperateDate);
