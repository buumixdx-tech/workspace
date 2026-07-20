
import requests
import pandas as pd
import datetime
from io import StringIO
import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from config_loader import CK_HOST, CK_AUTH

EXPECTED_START_DATE = pd.to_datetime("2021-01-01")
EXPECTED_END_DATE_THRESHOLD = pd.to_datetime(datetime.date.today()) - pd.Timedelta(days=10) # Allowing some lag

def query_ck(sql):
    try:
        r = requests.post(CK_HOST, params={'query': sql}, auth=CK_AUTH)
        if r.status_code == 200:
            if not r.text.strip(): return pd.DataFrame()
            return pd.read_csv(StringIO(r.text), sep='\t', names=['code', 'min_date', 'max_date', 'cnt'])
        print(f"Error: {r.text}")
    except Exception as e:
        print(e)
    return pd.DataFrame()

def get_securities():
    # Source Truth
    sql = "SELECT code, type, ipo_date, out_date FROM stock_data.securities_info FORMAT CSVWithNames"
    r = requests.post(CK_HOST, params={'query': sql}, auth=CK_AUTH)
    if r.status_code == 200:
        return pd.read_csv(StringIO(r.text))
    return pd.DataFrame()

def main():
    print(f"--- Data Verification Report ---")
    print(f"Target Start Date: {EXPECTED_START_DATE.date()}")
    print(f"Target End Date (Latest): >= {EXPECTED_END_DATE_THRESHOLD.date()}")
    
    # 1. Get Source Truth
    df_sec = get_securities()
    if df_sec.empty:
        print("CRITICAL: stock_data.securities_info is empty! Cannot verify against Baostock list.")
        return
        
    df_sec['ipo_date'] = pd.to_datetime(df_sec['ipo_date'], errors='coerce')
    df_sec['out_date'] = pd.to_datetime(df_sec['out_date'], errors='coerce')
    
    total_sec = len(df_sec)
    total_stocks_idx = df_sec[df_sec['type'].isin([1, 2])]
    print(f"Total Securities in Baostock List: {total_sec}")
    print(f"  - Stocks (Type 1): {len(df_sec[df_sec['type']==1])}")
    print(f"  - Indices (Type 2): {len(df_sec[df_sec['type']==2])}")

    # 2. Get Actual Data Stats from ClickHouse
    print("\nFetching Stock Data Stats from ClickHouse...")
    sql_stock = "SELECT code, min(date), max(date), count() FROM stock_data.stock_kline_day GROUP BY code"
    df_stock_stats = query_ck(sql_stock)
    
    print("Fetching Index Data Stats from ClickHouse...")
    sql_index = "SELECT code, min(date), max(date), count() FROM stock_data.index_kline_day GROUP BY code"
    df_index_stats = query_ck(sql_index)
    
    # 3. Validation Logic
    def validate(row, stats_df, kind):
        code = row['code']
        ipo = row['ipo_date']
        out = row['out_date']
        
        # Find in stats
        stat = stats_df[stats_df['code'] == code]
        if stat.empty:
            return 'Missing'
            
        min_date = pd.to_datetime(stat.iloc[0]['min_date'])
        max_date = pd.to_datetime(stat.iloc[0]['max_date'])
        count = stat.iloc[0]['cnt']
        
        # Check Start Date
        # Should be max(2021-01-01, ipo_date)
        # Allow 7 days slippage
        target_start = max(EXPECTED_START_DATE, ipo) if pd.notnull(ipo) else EXPECTED_START_DATE
        
        start_ok = min_date <= (target_start + pd.Timedelta(days=15)) # 15 days tolerance for holidays/suspensions
        
        # Check End Date
        # If delisted, end date should be close to out_date
        # If active, end date should be close to Today
        is_delisted = out < pd.to_datetime(datetime.date.today())
        
        if is_delisted:
            end_ok = abs((max_date - out).days) < 30 # Delisted stocks might stop trading earlier
        else:
            end_ok = max_date >= EXPECTED_END_DATE_THRESHOLD
            
        if not start_ok:
            return f'Late Start (Act: {min_date.date()}, Exp: {target_start.date()})'
        if not end_ok:
            return f'Early Stop (Act: {max_date.date()})'
            
        return 'OK'

    # Validate Stocks
    print("\n[Validating Stocks]")
    stocks = df_sec[df_sec['type'] == 1].copy()
    stocks['status'] = stocks.apply(lambda r: validate(r, df_stock_stats, 'Stock'), axis=1)
    
    ok_stocks = stocks[stocks['status'] == 'OK']
    print(f"✅ Qualified Stocks: {len(ok_stocks)} / {len(stocks)} ({len(ok_stocks)/len(stocks):.1%})")
    
    missing_stocks = stocks[stocks['status'] == 'Missing']
    if not missing_stocks.empty:
        print(f"❌ Missing Stocks ({len(missing_stocks)}): {missing_stocks['code'].head(5).tolist()}...")

    bad_start = stocks[stocks['status'].str.contains('Late Start')]
    if not bad_start.empty:
        print(f"⚠️ Late Start ({len(bad_start)}): {bad_start['code'].head(3).tolist()} (e.g. {bad_start.iloc[0]['status']})")
        
    bad_end = stocks[stocks['status'].str.contains('Early Stop')]
    if not bad_end.empty:
        print(f"⚠️ Early Stop ({len(bad_end)}): {bad_end['code'].head(3).tolist()} (e.g. {bad_end.iloc[0]['status']})")

    # Validate Indices
    print("\n[Validating Indices]")
    indices = df_sec[df_sec['type'] == 2].copy()
    # Indices don't strictly follow IPO date in securities_info usually (often missing), assume 2021-01-01
    indices['status'] = indices.apply(lambda r: validate(r, df_index_stats, 'Index'), axis=1)
    
    ok_indices = indices[indices['status'] == 'OK']
    print(f"✅ Qualified Indices: {len(ok_indices)} / {len(indices)} ({len(ok_indices)/len(indices):.1%})")
    
    missing_indices = indices[indices['status'] == 'Missing']
    if not missing_indices.empty:
        print(f"❌ Missing Indices ({len(missing_indices)}): Includes 399xxx etc.")

    print("\n--- Summary ---")
    print(f"Stocks Completeness: {len(ok_stocks)}/{len(stocks)}")
    print(f"Indices Completeness: {len(ok_indices)}/{len(indices)}")
    
if __name__ == "__main__":
    main()
