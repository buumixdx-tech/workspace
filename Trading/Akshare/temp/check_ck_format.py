import clickhouse_connect
import toml
import os

def check_code_format():
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
    
    tables = [
        "finance_concept_main",
        "finance_concept_components",
        "finance_concept_daily_rank",
        "analysis_hot_topic_mapping",
        "stock_snapshot_intraday"
    ]
    
    print("Database Verification:")
    for t in tables:
        try:
            sql = f"SELECT count() as cnt FROM {t}"
            df = client.query_df(sql)
            count = df['cnt'].iloc[0]
            print(f"✅ Table '{t}' exists. Rows: {count}")
        except Exception as e:
            print(f"❌ Table '{t}' Error: {e}")
            
    client.close()

if __name__ == "__main__":
    check_code_format()
