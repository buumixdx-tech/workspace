import pandas as pd
from market.ck_client import ClickHouseClient
import os

def debug_export():
    ck = ClickHouseClient()
    
    # Check latest date
    latest_date_df = ck.query_df("SELECT max(date) as max_date FROM stock_kline_day")
    latest_date = latest_date_df['max_date'].iloc[0]
    print(f"Latest date: {latest_date} ({type(latest_date)})")
    
    # Check types of code in both tables
    print("\nSchema of stock_kline_day:")
    print(ck.query_df("DESCRIBE stock_kline_day")[['name', 'type']])
    
    print("\nSchema of securities_info:")
    print(ck.query_df("DESCRIBE securities_info")[['name', 'type']])
    
    # Test join with cast
    sql = f"""
    SELECT 
        cast(k.code, 'String') as code, 
        any(i.symbol) as name,
        max(k.close * i.total_shares) as market_cap
    FROM stock_kline_day k
    JOIN securities_info i ON cast(k.code, 'String') = cast(i.code, 'String')
    WHERE k.date = '{latest_date}'
    GROUP BY code
    HAVING market_cap >= 5000000000 AND market_cap <= 120000000000
    ORDER BY market_cap DESC
    """
    
    print("\nExecuting query with cast...")
    df = ck.query_df(sql)
    
    if df.empty:
        print("No stocks found.")
    else:
        print(f"Found {len(df)} stocks.")
        output_path = os.path.join(os.getcwd(), "market_cap_stocks.csv")
        df[['code', 'name']].to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"Saved to {output_path}")

if __name__ == "__main__":
    debug_export()
