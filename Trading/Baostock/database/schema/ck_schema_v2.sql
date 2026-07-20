-- ============================================================
-- 方案设计：ClickHouse 表结构重构 2.0
-- 目标：标准化、高性能回测支持、策略计算友好
-- 数据库：stock_data (假设已存在)
-- ============================================================

-- ------------------------------------------------------------
-- 1. [核心] A股个股日线行情表 (stock_kline_day)
-- ------------------------------------------------------------
-- 变更点：
-- 1. 表名从 daily_k 改为 stock_kline_day，与 index_kline_day 区分。
-- 2. 字段类型优化：adjustflag(String->UInt8), tradestatus(UInt8)。
-- 3. 增加 MATERIALIZED 列，将原视图中的涨跌停计算下沉到物理表，加速查询。
-- 4. 引擎使用 ReplacingMergeTree，保证同一天同一只股票只有一条记录 (去重)。
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_data.stock_kline_day
(
    -- 维度键
    `code` LowCardinality(String) COMMENT '证券代码 (e.g. sh.600000)',
    `date` Date COMMENT '交易日期',
    
    -- 基础行情 (OHLCV)
    `open` Float32,
    `high` Float32,
    `low` Float32,
    `close` Float32,
    `preclose` Float32 COMMENT '前收盘价',
    `volume` UInt64 COMMENT '成交量(股)',
    `amount` Float64 COMMENT '成交额(元)',
    
    -- 状态指标
    `turn` Float32 COMMENT '换手率(%)',
    `pctChg` Float32 COMMENT '涨跌幅(%) Baostock原文字段',
    `tradestatus` UInt8 DEFAULT 1 COMMENT '交易状态(1:正常 0:停牌)',
    `isST` UInt8 DEFAULT 0 COMMENT '是否ST(0:否 1:是)',
    `adjustflag` UInt8 DEFAULT 3 COMMENT '复权标识 (3:不复权)',
    
    -- 元数据
    `update_time` DateTime DEFAULT now() COMMENT '数据最后写入时间',

    -- [策略计算加速列] (自动计算，无需插入)
    -- 注意：北交所涨跌幅限制为 30%，科创板/创业板 20%，主板 10% (ST 5%)
    -- 这里的逻辑可能不仅仅是简单的 code 前缀判断，还涉及历史规则变迁(创业板注册制改革时间点)。
    -- 为简化，先按现行规则硬编码，后续建议改为关联维表 `limit_rule`。
    `limit_ratio` Float32 MATERIALIZED multiIf(
        code LIKE 'bj.%', 0.3,
        code LIKE 'sh.688%', 0.2, 
        code LIKE 'sz.300%', 0.2, -- 粗略处理：创业板注册制前是10%，这里为了性能先统一
        isST = 1, 0.05, 
        0.1
    ) COMMENT '涨跌幅限制比例',
    
    `limit_up_price` Float32 MATERIALIZED round(preclose * (1 + limit_ratio), 2) COMMENT '涨停价',
    `limit_down_price` Float32 MATERIALIZED round(preclose * (1 - limit_ratio), 2) COMMENT '跌停价',
    
    -- 当日封板状态 (1:涨停封死 2:跌停封死 3:触板未封)
    -- 修正逻辑：close 等于 涨停价 且 high=low (一字板) 或 high>low
    `limit_status` UInt8 MATERIALIZED multiIf(
        close >= limit_up_price, 1, 
        close <= limit_down_price, 2,
        high >= limit_up_price AND close < limit_up_price, 3, -- 炸板
        0
    ) COMMENT '封板状态'

)
ENGINE = ReplacingMergeTree(update_time)
PARTITION BY toYYYYMM(date) -- 按月分区，管理文件粒度适中
ORDER BY (code, date) -- 按Code聚簇，优化单股回测速度
SETTINGS index_granularity = 8192;


-- ------------------------------------------------------------
-- 2. [核心] 指数日线行情表 (index_kline_day)
-- ------------------------------------------------------------
-- 变更点：独立建表，不与股票混用。
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_data.index_kline_day
(
    `code` LowCardinality(String) COMMENT '指数代码 (e.g. sh.000001)',
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
-- 3. [新增] 全局交易日历表 (trade_calendar)
-- ------------------------------------------------------------
-- 作用：所有策略回测的 Time Index 基准。
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_data.trade_calendar
(
    `exchange` LowCardinality(String) DEFAULT 'SSE' COMMENT '交易所(SSE/SZSE)',
    `date` Date COMMENT '自然日',
    `is_trading_day` UInt8 COMMENT '是否交易日(1=是, 0=周末/节假日)',
    `wday` UInt8 COMMENT '星期几(0=周一...6=周日) - 注意CK函数 toDayOfWeek是1-7',
    
    -- 增强字段：方便 Join
    `prev_trading_date` Date COMMENT '前一个交易日(如果是交易日则为自己前一天)',
    `next_trading_date` Date COMMENT '后一个交易日'
)
ENGINE = ReplacingMergeTree()
ORDER BY (exchange, date);


-- ------------------------------------------------------------
-- 4. [维持] 复权因子表 (adjust_factor)
-- ------------------------------------------------------------
-- 保持原结构，非常标准。
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_data.adjust_factor_v2
(
    `code` LowCardinality(String),
    `dividOperateDate` Date COMMENT '除权除息日',
    `foreAdjustFactor` Float64 COMMENT '前复权因子',
    `backAdjustFactor` Float64 COMMENT '后复权因子',
    `update_time` DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(update_time)
ORDER BY (code, dividOperateDate);


-- ------------------------------------------------------------
-- 5. [新增] 证券基础信息表 (securities_info)
-- ------------------------------------------------------------
-- 作用：管理个股生命周期（上市、退市、ST状态变更）。
-- 解决：Empty Dataframe 问题，或者非正常退市股的处理。
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_data.securities_info
(
    `code` LowCardinality(String),
    `symbol` String COMMENT '股票名称',
    `ipo_date` Date COMMENT '上市日期',
    `out_date` Date COMMENT '退市日期(如果未退市则为 Null 或 2999-01-01)',
    `type` UInt8 COMMENT '类型(1:股票 2:指数 3:ETF...)',
    `status` UInt8 COMMENT '当前状态(1:上市 0:退市 2:暂停上市)',
    `update_time` DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(update_time)
ORDER BY code;
