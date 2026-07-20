import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market.ck_client import ClickHouseClient

def init_snapshot_table():
    ck = ClickHouseClient()
    
    # 增加 source_time 字段
    # 先删除旧表
    drop_sql = "DROP TABLE IF EXISTS stock_snapshot_intraday"
    ck.command(drop_sql)
    print("Dropped old table.")
    
    create_sql = """
    CREATE TABLE stock_snapshot_intraday (
        code LowCardinality(String),
        name LowCardinality(String),
        
        
        snapshot_time DateTime,          -- 批次逻辑时间 (Batch Start Time)
        source_time DateTime64(3),       -- 交易所/服务器时间 (Source Time)
        
        price Float32,
        open Float32,
        high Float32,
        low Float32,
        last_close Float32,              -- 昨收
        
        change Float32,                  -- 涨跌额
        pct_chg Float32,                 -- 涨跌幅 (%)
        
        volume UInt64,                   -- 成交量 (单位使用: 股)
        amount Float64,                  -- 成交额 (单位使用: 元)
        
        turnover_rate Float32,           -- 换手率 (%)
        total_market_cap Float64,        -- 总市值 (元)
        float_market_cap Float64,        -- 流通市值 (元)
        is_suspended UInt8               -- 是否停牌 (1:停牌, 0:正常)
    ) 
    ENGINE = ReplacingMergeTree(snapshot_time)
    PARTITION BY toYYYYMMDD(snapshot_time)
    ORDER BY (code, snapshot_time)
    SETTINGS index_granularity = 8192
    """
    
    try:
        ck.command(create_sql)
        print("Successfully created table: stock_snapshot_intraday")
    except Exception as e:
        print(f"Error creating table: {e}")
    finally:
        ck.close()

if __name__ == "__main__":
    init_snapshot_table()
