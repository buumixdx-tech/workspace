
import baostock as bs
import pandas as pd
import requests
import datetime
import sys
import os

# 添加父目录到路径以便导入 config_loader
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config_loader import CK_HOST, CK_AUTH

START_DATE = "1990-12-19" # SSE Established
END_DATE = "2026-12-31"   # Future

def get_trade_dates():
    print(f"Fetching trade dates from {START_DATE} to {END_DATE}...")
    lg = bs.login()
    if lg.error_code != '0':
        print(f"Login failed: {lg.error_msg}")
        return None

    rs = bs.query_trade_dates(start_date=START_DATE, end_date=END_DATE)
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    
    bs.logout()
    
    if not data_list:
        print("No trade dates found.")
        return None
        
    # Baostock returns inconsistent columns sometimes
    # Usually: calendar_date, is_trading_day
    # Sometimes: exchange, calendar_date, is_trading_day
    
    first_row = data_list[0]
    if len(first_row) == 3:
        cols = ['exchange', 'date', 'is_trading_day']
    elif len(first_row) == 2:
        cols = ['date', 'is_trading_day']
    else:
        print(f"Unexpected column count: {len(first_row)}")
        return None

    df = pd.DataFrame(data_list, columns=cols)
    
    # Normalize to ensure we have 'calendar_date' accessible as 'calendar_date' for logic below
    # Logic below expects 'calendar_date' column name
    if 'date' in df.columns:
        df.rename(columns={'date': 'calendar_date'}, inplace=True)
        
    return df

def process_calendar(df):
    # Enrich data for ClickHouse
    # Schema: exchange, date, is_trading_day, wday, prev_trading_date, next_trading_date
    
    # Baostock default exchange is SH/SZ unified calendar mostly
    # We will replicate for 'SSE' and 'SZSE' or just use 'SSE' as main
    
    df['date_dt'] = pd.to_datetime(df['calendar_date'])
    df['is_trading_day'] = df['is_trading_day'].astype(int)
    
    # 1. wday (0=Mon, 6=Sun)
    df['wday'] = df['date_dt'].dt.dayofweek
    
    # 2. Calculate prev/next trading days
    # Filter only trading days to find shifts
    trading_days = df[df['is_trading_day'] == 1]['date_dt'].sort_values().reset_index(drop=True)
    
    # We can do a merge_asof logic or mapped lookup
    # Because calendar is continuous, we need to map FOR EVERY DATE what is the prev/next TRADING date
    
    # Create a lookup mapping from any date to prev/next trading date
    # Convert series to list for faster lookup
    td_set = set(trading_days)
    td_list = trading_days.tolist()
    
    # Optimized: Use searchsorted
    import numpy as np
    
    # For every date in df, find index in trading_days
    # searchsorted(side='right') - 1  -> Previous Trading Day (if current is trading, it returns itself? No we want strict PREV?)
    # Valid Convention:
    #   If Today is Trading Day: Prev is Yesterday(if trading)
    #   If Today is Saturday: Prev is Friday
    
    # Let's simple use 'ffill' on a specific column
    df_trading = df[['date_dt']].copy()
    df_trading['last_trade'] = df.apply(lambda x: x['date_dt'] if x['is_trading_day'] == 1 else pd.NaT, axis=1)
    
    # Forward fill to get "Previous or Current"
    # But strictly "Previous" means < date
    # Let's stick to simple logic:
    # Join with next closest value
    
    # To facilitate Vectorized operations:
    # 1. is_trading_day mask
    mask = df['is_trading_day'] == 1
    
    # 2. Get shifted arrays for logic
    # It's surprisingly complex to do "If Sunday, Prev is Friday" efficiently without loop.
    # Simpler approach:
    # A. Mark trading days
    # B. FFill on 'trading_date' column gives "Most recent trading day (<= today)"
    # C. BFill on 'trading_date' column gives "Next trading day (>= today)"
    
    dates = df['date_dt'].values
    is_trade = df['is_trading_day'].values
    
    # Extract trading dates
    valid_dates = dates[is_trade == 1]
    
    # Use searchsorted
    # index of the first valid_date >= current_date
    idx_next = np.searchsorted(valid_dates, dates, side='left')
    # index of the first valid_date > current_date
    idx_strict_next = np.searchsorted(valid_dates, dates, side='right')
    
    # index of the last valid_date <= current_date
    idx_prev = np.searchsorted(valid_dates, dates, side='right') - 1
    # index of the last valid_date < current_date
    idx_strict_prev = np.searchsorted(valid_dates, dates, side='left') - 1
    
    # Map to dates, handling bounds
    def get_date_safe(arr, indices):
        res = []
        for i in indices:
            if 0 <= i < len(arr):
                res.append(arr[i])
            else:
                res.append(None) # Out of bound
        return res

    # Logic decision: 
    # prev_trading_date: Strictly < Date ? Or "Effective Business Date"? 
    # Usually "Business Date" for Saturday IS Friday. 
    # But "Prev Trading Date" usually implies T-1.
    # Let's assume Business Date semantics: 
    # If today is Monday(Trade), Prev is Friday. Next is Tuesday. 
    # If today is Saturday, Prev is Friday. Next is Monday.
    
    df['prev_trading_date'] = get_date_safe(valid_dates, idx_strict_prev)
    df['next_trading_date'] = get_date_safe(valid_dates, idx_strict_next)
    
    # Format to string
    df['prev_trading_date'] = pd.to_datetime(df['prev_trading_date']).dt.strftime('%Y-%m-%d')
    df['next_trading_date'] = pd.to_datetime(df['next_trading_date']).dt.strftime('%Y-%m-%d')
    # Handle NaTs
    df['prev_trading_date'] = df['prev_trading_date'].fillna('1900-01-01')
    df['next_trading_date'] = df['next_trading_date'].fillna('2999-01-01')

    # Prepare for insert
    # Duplicate for 'SSE' and 'SZSE' just in case, or just use 'SSE' default
    # Schema: exchange, date, is_trading_day, wday, prev, next
    
    out_rows = []
    exchanges = ['SSE', 'SZSE'] # Support both
    
    for idx, row in df.iterrows():
        d = row['calendar_date']
        is_t = row['is_trading_day']
        w = row['wday']
        p = row['prev_trading_date']
        n = row['next_trading_date']
        
        for ex in exchanges:
            out_rows.append(f"('{ex}', '{d}', {is_t}, {w}, '{p}', '{n}')")
            
    return out_rows

def insert_ck(rows):
    if not rows:
        return
    
    print(f"Inserting {len(rows)} rows into ClickHouse...")
    
    # Chunking
    chunk_size = 5000
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i+chunk_size]
        values = ",".join(chunk)
        sql = f"INSERT INTO stock_data.trade_calendar VALUES {values}"
        
        try:
            r = requests.post(CK_HOST, data=sql, auth=CK_AUTH)
            if r.status_code != 200:
                print(f"Error: {r.text}")
                break
        except Exception as e:
            print(f"Exception: {e}")
            break
            
    print("Done.")

def main():
    df = get_trade_dates()
    if df is not None:
        rows = process_calendar(df)
        insert_ck(rows)


def run_etl():
    """External entry point for UI."""
    try:
        df = get_trade_dates()
        if df is not None:
            rows = process_calendar(df)
            insert_ck(rows)
            return True, "Trading calendar updated successfully."
        else:
            return False, "Failed to fetch trade dates."
    except Exception as e:
        return False, f"ETL Error: {e}"

if __name__ == "__main__":
    main()

