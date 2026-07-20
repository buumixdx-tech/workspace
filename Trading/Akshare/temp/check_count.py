from market.ck_client import ClickHouseClient
import pandas as pd

def check_count():
    ck = ClickHouseClient()
    
    try:
        print("Checking stock_kline_day...")
        sql = "SELECT count(*) as count FROM stock_kline_day WHERE date = '2026-01-28'"
        df = ck.query_df(sql)
        print(f"Count in stock_kline_day for 2026-01-28: {df['count'].iloc[0]}")
    except Exception as e:
        print(f"Failed to query stock_kline_day: {e}")
        
        # If failed, list tables to help debug
        try:
            print("\nListing all tables in database:")
            df_tables = ck.query_df("SHOW TABLES")
            print(df_tables)
        except Exception as e2:
            print(f"Failed to show tables: {e2}")

if __name__ == "__main__":
    check_count()
