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
    # Handle both datetime and date objects
    if hasattr(latest_date, 'strftime'):
        date_str = latest_date.strftime('%Y-%m-%d')
    else:
        date_str = str(latest_date)
        
    print(f"Latest date: {date_str}")
    
    # 2. Query for market cap
    # We join stock_kline_day (latest close) with securities_info (total shares)
    # Using Subquery for the date to be safe
    sql = f"""
    SELECT 
        k.code as code, 
        i.symbol as name,
        k.close * i.total_shares as mkt_cap
    FROM stock_kline_day k
    JOIN securities_info i ON k.code = i.code
    WHERE k.date = '{date_str}'
      AND k.close > 0
      AND i.total_shares > 0
    """
    
    print("Fetching data and calculating market cap...")
    df = ck.query_df(sql)
    
    if df.empty:
        print("No data retrieved from join.")
        return
    
    # 3. Filter in memory (sometimes safer than complex ClickHouse JOINS if types are tricky, 
    # but here we'll try to do it right)
    # Actually let's just filter in Pandas to be sure about units
    # 5B = 5 * 10^9, 120B = 120 * 10^9
    df = df[(df['mkt_cap'] >= 5000000000) & (df['mkt_cap'] <= 120000000000)]
    df = df.sort_values('mkt_cap', ascending=False)
    
    if df.empty:
        print("No stocks found in the specified market cap range.")
        return
    
    # 4. Save to CSV
    output_path = os.path.join(os.getcwd(), "market_cap_stocks.csv")
    df[['code', 'name']].to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"Successfully exported {len(df)} stocks to {output_path}")
    print(df.head())

if __name__ == "__main__":
    export_market_cap()
