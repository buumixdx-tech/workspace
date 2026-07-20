
import pandas as pd
import clickhouse_connect
import os

def filter_small_cap_stocks():
    # File configuration
    output_file = r'd:\WorkSpace\Trading\Akshare\data\stock_analysis\sm.xlsx'
    
    # 1. Connect to ClickHouse
    try:
        client = clickhouse_connect.get_client(
            host='localhost', 
            port=8123, 
            username='admin', 
            password='admin_password', 
            database='stock_data'
        )
        print("Connected to ClickHouse.")
    except Exception as e:
        print(f"Error connecting to ClickHouse: {e}")
        return

    # 2. Execute Query
    # Filter: Float Market Cap < 1.5 Billion, Exclude BJ (bj.), ChiNext (sz.30), STAR (sh.68)
    # Using 'NOT LIKE' for string matching assumes standard Akshare/ClickHouse code formats.
    query = """
    SELECT 
        code, 
        name, 
        total_market_cap, 
        float_market_cap, 
        is_suspended,
        snapshot_time
    FROM stock_snapshot_intraday 
    WHERE snapshot_time = (SELECT max(snapshot_time) FROM stock_snapshot_intraday)
      AND float_market_cap > 0
      AND float_market_cap < 1500000000
      AND code NOT LIKE 'bj.%'
      AND code NOT LIKE 'sz.30%'
      AND code NOT LIKE 'sh.68%'
      AND name NOT LIKE '%ST%'
    ORDER BY float_market_cap ASC
    """
    
    print("Executing query...")
    try:
        df = client.query_df(query)
    except Exception as e:
        print(f"Error executing query: {e}")
        return

    if df.empty:
        print("No stocks found matching the criteria.")
        return

    print(f"Found {len(df)} stocks.")
    print(f"Data time: {df['snapshot_time'].iloc[0]}")

    # 3. Process Data to match Excel headers
    # Headers: ['股票代码', '股票简称', '总市值', '流通市值', '交易状态', '停牌日期', '是否st']
    
    # Map columns
    result_df = pd.DataFrame()
    result_df['股票代码'] = df['code']
    result_df['股票简称'] = df['name']
    result_df['总市值'] = df['total_market_cap']
    result_df['流通市值'] = df['float_market_cap']
    
    # Transform '交易状态'
    # 0 -> 正常, 1 -> 停牌 (Assuming is_suspended 1 means suspended)
    result_df['交易状态'] = df['is_suspended'].apply(lambda x: '停牌' if x == 1 else '正常')
    
    # '停牌日期' - leave empty as we don't have this specific info in snapshot
    result_df['停牌日期'] = None
    
    # '是否st' - infer from name
    # Using simple check if 'ST' is in the name. Note: This handles 'ST', '*ST', 'S*ST', etc.
    result_df['是否st'] = df['name'].apply(lambda x: '是' if 'ST' in str(x).upper() else '否')

    # Ensure output directory exists (though file likely exists per user request)
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 4. Save to Excel
    print(f"Saving to {output_file}...")
    try:
        # index=False to exclude dataframe index
        result_df.to_excel(output_file, index=False)
        print("Successfully saved.")
    except Exception as e:
        print(f"Error saving Excel file: {e}")
        # Identify permission error
        if "Permission denied" in str(e):
            print("Please close the Excel file if it is open and try again.")

if __name__ == "__main__":
    filter_small_cap_stocks()
