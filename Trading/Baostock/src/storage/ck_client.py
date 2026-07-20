
import requests
import pandas as pd
from io import StringIO
import os
import sys

# 使用统一配置加载器
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config_loader import get_clickhouse_config

class ClickHouseClient:
    def __init__(self, host=None, auth=None):
        # 从统一配置加载器获取配置
        config_host, config_auth = get_clickhouse_config()
        
        self.host = host or config_host
        self.auth = auth or config_auth
        
    def query(self, sql):
        """Execute non-selecting SQL (INSERT, DDL)"""
        try:
            r = requests.post(self.host, params={'query': sql}, auth=self.auth)
            if r.status_code != 200:
                raise Exception(f"ClickHouse Error ({r.status_code}): {r.text}")
            return r.text.strip()
        except Exception as e:
            raise e

    def execute_query(self, sql):
        """Alias for query to match app.py usage"""
        return self.query(sql)


    def query_df(self, sql):
        """Execute SELECT and return DataFrame"""
        try:
            # Use 'FORMAT CSVWithNames' for robust parsing
            if 'FORMAT' not in sql.upper():
                sql += " FORMAT CSVWithNames"
                
            r = requests.post(self.host, params={'query': sql}, auth=self.auth)
            if r.status_code != 200:
                raise Exception(f"ClickHouse Error ({r.status_code}): {r.text}")
            
            # Check if empty (only header or empty string)
            if not r.text.strip():
                return pd.DataFrame()
                
            return pd.read_csv(StringIO(r.text))
        except Exception as e:
            print(f"CkClient Exception: {e}")
            return pd.DataFrame()

# Global Instance
ck_client = ClickHouseClient()
