
import sys
import os
import json

# Add src to path to import ck_client
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from storage.ck_client import ck_client

def scan_schema():
    # 1. Get all tables and views in stock_data
    tables_query = "SELECT name, engine, comment FROM system.tables WHERE database = 'stock_data'"
    tables_df = ck_client.query_df(tables_query)
    
    schema = {}
    for table_name in tables_df['name']:
        cols_query = f"SELECT name, type, comment FROM system.columns WHERE database = 'stock_data' AND table = '{table_name}' ORDER BY position"
        cols_df = ck_client.query_df(cols_query)
        schema[table_name] = cols_df.to_dict(orient='records')
    
    print(json.dumps(schema, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    scan_schema()
