import pandas as pd
from market.ck_client import ClickHouseClient
import os

def export_market_cap():
    ck = ClickHouseClient()
    
    # Use stock_snapshot_intraday as it contains the correctly calculated market cap
    # We take the latest snapshot for each stock
    sql = """
    SELECT 
        code, 
        argMax(name, snapshot_time) as name, 
        argMax(total_market_cap, snapshot_time) as mkt_cap
    FROM stock_snapshot_intraday
    GROUP BY code
    """
    
    print("Fetching market cap data from intraday snapshots...")
    df = ck.query_df(sql)
    
    if df.empty:
        print("No snapshot data found.")
        return
    
    # Range: 50亿 to 120亿
    # 50亿 = 5,000,000,000
    # 120亿 = 12,000,000,000
    lower = 5e9
    upper = 12e9
    
    print(f"Filtering range: {lower:,.0f} to {upper:,.0f}...")
    
    filtered_df = df[(df['mkt_cap'] >= lower) & (df['mkt_cap'] <= upper)].copy()
    filtered_df = filtered_df.sort_values('mkt_cap', ascending=False)
    
    print(f"Total stocks matching criteria: {len(filtered_df)}")
    
    # Save to CSV (Requirement: stock code and stock name)
    output_path = "market_cap_stocks.csv"
    filtered_df[['code', 'name']].to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"Result successfully exported to {os.path.abspath(output_path)}")
    if not filtered_df.empty:
        print("\nTop 5 results:")
        print(filtered_df.head())

if __name__ == "__main__":
    export_market_cap()
