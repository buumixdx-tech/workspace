import pandas as pd
from market.ck_client import ClickHouseClient
import os

def export_market_cap():
    ck = ClickHouseClient()
    
    # 1. Get the latest date
    latest_date_df = ck.query_df("SELECT max(date) as max_date FROM stock_kline_day")
    if latest_date_df.empty or latest_date_df['max_date'].iloc[0] is None:
        print("No daily kline data found.")
        return
    
    latest_date = latest_date_df['max_date'].iloc[0]
    date_str = latest_date.strftime('%Y-%m-%d') if hasattr(latest_date, 'strftime') else str(latest_date)
    print(f"Target Date: {date_str}")
    
    # 2. Fetch close prices and total shares separately or simple join
    # Avoid calculation in SQL to sidestep potential type issues in ClickHouse driver
    sql = f"""
    SELECT 
        k.code, 
        i.symbol as name,
        k.close,
        i.total_shares
    FROM stock_kline_day k
    JOIN securities_info i ON k.code = i.code
    WHERE k.date = '{date_str}'
      AND i.type = 1
    """
    
    print("Fetching data...")
    df = ck.query_df(sql)
    
    if df.empty:
        print("No data retrieved.")
        return
    
    # 3. Calculate and Filter in Pandas
    print("Calculating market cap and filtering...")
    # Convert to numeric just in case
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['total_shares'] = pd.to_numeric(df['total_shares'], errors='coerce')
    
    df['market_cap'] = df['close'] * df['total_shares']
    
    # Range: 5 billion to 120 billion
    # 50亿 = 5,000,000,000
    # 120亿 = 120,000,000,000
    lower = 5e9
    upper = 120e9
    
    filtered_df = df[(df['market_cap'] >= lower) & (df['market_cap'] <= upper)].copy()
    filtered_df = filtered_df.sort_values('market_cap', ascending=False)
    
    print(f"Stocks matching criteria: {len(filtered_df)}")
    
    # 4. Save to CSV
    output_path = "market_cap_stocks.csv"
    filtered_df[['code', 'name']].to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"Result saved to {os.path.abspath(output_path)}")
    if not filtered_df.empty:
        print("\nTop 5 results:")
        print(filtered_df[['code', 'name', 'market_cap']].head())

if __name__ == "__main__":
    export_market_cap()
