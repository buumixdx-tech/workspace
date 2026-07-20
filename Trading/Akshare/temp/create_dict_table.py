from market.ck_client import ClickHouseClient

def create_table():
    ck = ClickHouseClient()
    sql = """
    CREATE TABLE IF NOT EXISTS dict_concept_mapping (
        `concept_id` UInt16 COMMENT '压缩协议用的 2 字节 ID',
        `concept_name` String COMMENT '板块名称',
        `update_date` Date DEFAULT toDate(now()) COMMENT '生成日期 (版本号)'
    ) ENGINE = ReplacingMergeTree(update_date)
    ORDER BY concept_id
    SETTINGS index_granularity = 8192
    """
    try:
        ck.command(sql)
        print("Table dict_concept_mapping created successfully or already exists.")
    except Exception as e:
        print(f"Error creating table: {e}")

if __name__ == "__main__":
    create_table()
