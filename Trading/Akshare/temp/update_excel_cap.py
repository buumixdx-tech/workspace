
import pandas as pd
import clickhouse_connect
import os

def update_excel_market_cap():
    file_path = r'd:\WorkSpace\Trading\Akshare\data\stock_analysis\select.xlsx'
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    # 1. Read Excel (Assuming no header based on inspection)
    print(f"Reading {file_path}...")
    try:
        df = pd.read_excel(file_path, header=None)
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return

    # 2. Connect to ClickHouse
    try:
        client = clickhouse_connect.get_client(
            host='localhost', 
            port=8123, 
            username='admin', 
            password='admin_password', 
            database='stock_data'
        )
    except Exception as e:
        print(f"Error connecting to ClickHouse: {e}")
        return

    # 3. Fetch latest market cap data
    # We use the snapshot table we just populated, which has today's closing data
    print("Fetching market cap data from ClickHouse...")
    query = """
    SELECT 
        code, 
        total_market_cap, 
        float_market_cap 
    FROM stock_snapshot_intraday 
    WHERE snapshot_time = (SELECT max(snapshot_time) FROM stock_snapshot_intraday)
    """
    ck_df = client.query_df(query)
    
    if ck_df.empty:
        print("No data found in ClickHouse snapshot.")
        return

    # 4. Prepare for Merge
    # Excel code format example: 'SZ.301176'
    # ClickHouse code format example: 'sz.301176' (need to verify normalization)
    # We will normalize Excel codes to lowercase for matching
    
    # Assuming Column 0 contains the stock code
    # Create a temporary column for matching
    df['match_code'] = df[0].astype(str).str.lower().str.strip()
    ck_df['code'] = ck_df['code'].astype(str).str.lower().str.strip()

    # 5. Merge
    print("Merging data...")
    merged_df = pd.merge(df, ck_df, left_on='match_code', right_on='code', how='left')

    # 6. Clean up
    # Remove temporary matching columns
    # 'match_code' is from df, 'code' is from ck_df
    # We want to keep original df columns + total_market_cap + float_market_cap
    
    # Identify original columns
    original_cols = df.columns.tolist()
    if 'match_code' in original_cols:
        original_cols.remove('match_code')
        
    # Select columns to keep
    # We want valid columns from merged_df
    final_cols = original_cols + ['total_market_cap', 'float_market_cap']
    
    final_df = merged_df[final_cols]
    
    # Fill NaN with 0 or empty? Let's keep as NaN or 0.
    # User might prefer blank if no data. 
    # But for numerical columns, maybe 0.
    # Let's leave as is (NaN) for now, pandas writes empty cell.
    
    # Optional: Format or Round?
    # User previously asked for exact values.
    # But usually 'total_market_cap' is in Yuan (e.g. 2,000,000,000). 
    
    # 7. Save back to Excel
    print(f"Saving updated file to {file_path}...")
    try:
        # Use header=False to match the read format (no header)
        final_df.to_excel(file_path, index=False, header=False)
        print("Done.")
    except Exception as e:
        print(f"Error saving Excel: {e}")
        # Try saving to a new file if permission denied
        temp_path = file_path.replace('.xlsx', '_updated.xlsx')
        print(f"Trying to save to {temp_path} instead...")
        final_df.to_excel(temp_path, index=False, header=False)
        print(f"Saved to {temp_path}")

if __name__ == "__main__":
    update_excel_market_cap()
