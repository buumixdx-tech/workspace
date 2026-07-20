import clickhouse_connect
import toml
import os
import pandas as pd

def check_snapshot_times():
    config_path = r"d:\WorkSpace\Trading\Akshare\config.toml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = toml.load(f)["clickhouse"]
    
    client = clickhouse_connect.get_client(
        host=config.get("host", "127.0.0.1"),
        port=config.get("port", 8123),
        username=config.get("user", "default"),
        password=config.get("password", ""),
        database=config.get("database", "default")
    )
    
    sql = """
    SELECT 
        code, 
        name,
        snapshot_time, 
        formatDateTime(source_time, '%Y-%m-%d %H:%i:%S.%f') as source_time_ms,
        formatDateTime(local_time, '%Y-%m-%d %H:%i:%S.%f') as local_time_ms
    FROM stock_snapshot_intraday 
    ORDER BY snapshot_time DESC, local_time DESC 
    LIMIT 20
    """
    
    df = client.query_df(sql)
    
    if not df.empty:
        print(f"Sample Records from stock_snapshot_intraday:")
        # 调整显示宽度
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        pd.set_option('display.max_colwidth', 50)
        print(df[['code', 'name', 'snapshot_time', 'source_time_ms', 'local_time_ms']])
        
        # 简单统计
        print("\n--- Statistics ---")
        count_sql = "SELECT count() as cnt FROM stock_snapshot_intraday"
        count = client.query_df(count_sql)['cnt'].iloc[0]
        distinct_times_sql = "SELECT count(distinct snapshot_time) as batches FROM stock_snapshot_intraday"
        batches = client.query_df(distinct_times_sql)['batches'].iloc[0]
        
        print(f"Total Rows: {count}")
        print(f"Total Batches (snapshot_time): {batches}")
    else:
        print("No data found in stock_snapshot_intraday")
    
    client.close()

if __name__ == "__main__":
    check_snapshot_times()
