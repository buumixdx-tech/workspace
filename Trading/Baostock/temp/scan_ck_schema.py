
import sys
import os
import pandas as pd

# Add src to path to import ck_client
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from storage.ck_client import ck_client

def scan_schema():
    # 1. Get all tables and views in stock_data
    tables_query = "SELECT name, engine, comment FROM system.tables WHERE database = 'stock_data'"
    tables_df = ck_client.query_df(tables_query)
    
    if tables_df.empty:
        print("No tables found in stock_data database.")
        return

    print("Found Tables/Views:")
    print(tables_df)
    print("\n" + "="*50 + "\n")

    # 2. Get columns for each table
    for index, row in tables_df.iterrows():
        table_name = row['name']
        print(f"Table: {table_name}")
        cols_query = f"SELECT name, type, comment FROM system.columns WHERE database = 'stock_data' AND table = '{table_name}' ORDER BY position"
        cols_df = ck_client.query_df(cols_query)
        print(cols_df)
        print("-" * 30)

if __name__ == "__main__":
    scan_schema()
