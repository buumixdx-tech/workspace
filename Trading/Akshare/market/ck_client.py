import clickhouse_connect
import pandas as pd
import toml
import os
from datetime import datetime

class ClickHouseClient:
    """
    ClickHouse 客户端工具类，用于与本地部署的 ClickHouse 进行通信。
    连接参数从根目录的 config.toml 中读取。
    """
    def __init__(self, config_path=None):
        if config_path is None:
            # 默认查找根目录下的 config.toml
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.toml")
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found at: {config_path}")
            
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = toml.load(f)["clickhouse"]
        
        self.client = None
        self._connect()

    def _connect(self):
        """建立连接"""
        try:
            self.client = clickhouse_connect.get_client(
                host=self.config.get("host", "127.0.0.1"),
                port=self.config.get("port", 8123),
                username=self.config.get("user", "default"),
                password=self.config.get("password", ""),
                database=self.config.get("database", "default")
            )
            # print(f"Successfully connected to ClickHouse: {self.config.get('host')}")
        except Exception as e:
            print(f"Failed to connect to ClickHouse: {e}")
            raise

    def query_df(self, sql: str, parameters: dict = None) -> pd.DataFrame:
        """
        执行查询并返回 Pandas DataFrame
        """
        try:
            return self.client.query_df(sql, parameters=parameters)
        except Exception as e:
            print(f"Query Error: {e}")
            return pd.DataFrame()

    def command(self, sql: str, parameters: dict = None):
        """
        执行命令（无返回结果，如 INSERT, UPDATE, DROP 等）
        """
        try:
            return self.client.command(sql, parameters=parameters)
        except Exception as e:
            print(f"Command Error: {e}")
            raise

    def insert_df(self, table_name: str, df: pd.DataFrame):
        """
        将 DataFrame 插入指定的表
        """
        if df.empty:
            return
        try:
            self.client.insert_df(table_name, df)
        except Exception as e:
            print(f"Insert Error into {table_name}: {e}")
            raise

    def close(self):
        """关闭连接"""
        if self.client:
            self.client.close()

# 示例使用方法:
if __name__ == "__main__":
    try:
        ck = ClickHouseClient()
        # 测试读取过去一年的日K数据量
        test_sql = "SELECT count() as cnt FROM stock_kline_day"
        res = ck.query_df(test_sql)
        print(f"Current stock_kline_day record count: {res['cnt'].iloc[0] if not res.empty else 0}")
    except Exception as e:
        print(f"Error: {e}")
