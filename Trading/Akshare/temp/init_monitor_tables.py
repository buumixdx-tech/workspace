import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market.ck_client import ClickHouseClient

def init_monitoring_tables():
    ck = ClickHouseClient()
    
    # 1. finance_concept_main
    # 以后 name 就是主键
    print("Creating finance_concept_main...")
    ck.command("DROP TABLE IF EXISTS finance_concept_main")
    ck.command("""
    CREATE TABLE finance_concept_main (
        name LowCardinality(String),
        source LowCardinality(String),
        update_time DateTime DEFAULT now()
    ) ENGINE = ReplacingMergeTree(update_time)
    ORDER BY (name)
    """)

    # 2. finance_concept_components
    # concept_name 关联股票
    print("Creating finance_concept_components...")
    ck.command("DROP TABLE IF EXISTS finance_concept_components")
    ck.command("""
    CREATE TABLE finance_concept_components (
        concept_name LowCardinality(String),
        stock_code LowCardinality(String),
        update_time DateTime DEFAULT now()
    ) ENGINE = ReplacingMergeTree(update_time)
    ORDER BY (concept_name, stock_code)
    """)

    # 3. concept_snapshot_intraday
    # 核心快照表，由 concept_name 标识
    print("Creating concept_snapshot_intraday...")
    ck.command("DROP TABLE IF EXISTS concept_snapshot_intraday")
    ck.command("""
    CREATE TABLE concept_snapshot_intraday (
        concept_name LowCardinality(String),
        date Date,
        snapshot_time DateTime,
        
        price_index Float64,     -- 当前指数
        pct_chg Float32,         -- 涨跌幅 (%)
        change Float32,          -- 涨跌额
        
        volume Float64,          -- 成交量 (万手)
        amount Float64,          -- 成交额 (亿元)
        turnover_rate Float32,   -- 加权换手率 (%)
        
        rise_count UInt32,       -- 上涨家数
        fall_count UInt32,       -- 下跌家数
        flat_count UInt32,       -- 平盘家数
        limit_up_count UInt32,   -- 涨停家数
        limit_down_count UInt32, -- 跌停家数
        suspended_count UInt32,  -- 停牌家数
        
        open Float64,            -- 今开
        high Float64,            -- 最高
        low Float64,             -- 最低
        last_close Float64       -- 昨收
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMMDD(date)
    ORDER BY (date, snapshot_time, concept_name)
    """)

    # 4. analysis_hot_topic_mapping
    # 存储“个股-热门板块”的 AI 推理关联关系
    print("Creating analysis_hot_topic_mapping...")
    ck.command("DROP TABLE IF EXISTS analysis_hot_topic_mapping")
    ck.command("""
    CREATE TABLE analysis_hot_topic_mapping (
        concept_name LowCardinality(String), -- 关联的热门板块/概念名称
        stock_code String,                 -- 股票代码
        stock_name String,                 -- 股票名称
        reason String,                     -- 关联理由与深度描述
        update_time DateTime DEFAULT now()
    ) ENGINE = ReplacingMergeTree(update_time)
    ORDER BY (concept_name, stock_code)
    """)

    print("All concept-related tables updated to use concept_name.")

    # 5. Optimization Views
    # 建立“精选板块成分视图”
    print("Creating optimization views...")
    ck.command("DROP TABLE IF EXISTS view_concept_components_filtered")
    ck.command("DROP TABLE IF EXISTS view_selected_concept_list") # Drop dependent view first if needed, but here order is reversed for creation

    # 5.1 核心板块名单视图 (过滤掉成分股 > 300 的板块)
    ck.command("""
    CREATE VIEW view_selected_concept_list AS
    SELECT concept_name
    FROM finance_concept_components
    GROUP BY concept_name
    HAVING count() <= 300
    """)

    # 5.2 精选成分股映射视图 (只保留精选板块的成分股)
    ck.command("""
    CREATE VIEW view_concept_components_filtered AS
    SELECT 
        c.concept_name,
        c.stock_code,
        c.update_time
    FROM finance_concept_components c
    INNER JOIN view_selected_concept_list s ON c.concept_name = s.concept_name
    """)
    print("Optimization views created.")
    ck.close()

if __name__ == "__main__":
    init_monitoring_tables()
