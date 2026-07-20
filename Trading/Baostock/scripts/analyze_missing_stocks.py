
import baostock as bs
import pandas as pd
import requests
import datetime
from io import StringIO
import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from config_loader import CK_HOST, CK_AUTH

# 1. Load the Strict List (Target)
# We assume the user just generated 'ashare_list_20260122.md' or we can regenerate in memory.
# Let's regenerate to be self-contained.

def is_a_stock(code):
    if code.startswith('sh.60') or code.startswith('sh.68'): return True
    if code.startswith('sz.00') or code.startswith('sz.30'): return True
    if code.startswith('bj.4') or code.startswith('bj.8'): return True
    return False

def get_target_list():
    print("Fetching target list from Baostock...")
    bs.login()
    rs = bs.query_all_stock(day="2026-01-21")
    data = []
    while rs.next():
        data.append(rs.get_row_data())
    
    df = pd.DataFrame(data, columns=['code', 'tradeStatus', 'code_name'])
    df = df[df['code'].apply(is_a_stock)]
    return df['code'].tolist()

def get_ck_list():
    print("Fetching existing list from ClickHouse...")
    # Get distinct codes from stock_kline_day
    sql = "SELECT DISTINCT code FROM stock_data.stock_kline_day"
    r = requests.post(CK_HOST, params={'query': sql}, auth=CK_AUTH)
    if r.status_code == 200 and r.text.strip():
        return r.text.strip().split('\n')
    return []

def analyze_missing(missing_codes):
    print(f"\nAnalyzing {len(missing_codes)} missing stocks...")
    
    # We are already logged in from get_target_list (if not logout).
    # bs login is global.
    
    report = []
    
    for code in missing_codes:
        # Try to fetch history to see if data exists ANYWHERE
        # Query from 1990 to 2026
        # Just fetch first row?
        fields = "date,code,open,close"
        rs = bs.query_history_k_data_plus(code, fields, start_date="1990-01-01", end_date="2026-12-31", frequency="d", adjustflag="3")
        
        has_data = False
        min_date = "N/A"
        max_date = "N/A"
        
        # Check first row
        data_rows = []
        while rs.next():
            data_rows.append(rs.get_row_data())
            
        if data_rows:
            has_data = True
            min_date = data_rows[0][0] # date column
            max_date = data_rows[-1][0]
            
        report.append({
            'code': code,
            'has_data': has_data,
            'min_date': min_date,
            'max_date': max_date
        })
        
    bs.logout()
    
    return pd.DataFrame(report)

def main():
    target_codes = set(get_target_list())
    ck_codes = set(get_ck_list())
    
    missing = list(target_codes - ck_codes)
    missing.sort()
    
    print(f"Target: {len(target_codes)}")
    print(f"ClickHouse: {len(ck_codes)}")
    print(f"Missing: {len(missing)}")
    
    if not missing:
        print("No missing stocks!")
        bs.logout()
        return

    df_report = analyze_missing(missing)
    
    print("\n--- Mission Report ---")
    print(df_report.to_markdown(index=False))
    
    # Analyze Pattern
    # Group by prefix
    # Group by has_data
    
    print("\nSummary:")
    print(f"Truly Empty in Baostock: {len(df_report[~df_report['has_data']])}")
    print(f"Has Data but missing in CK: {len(df_report[df_report['has_data']])}")

if __name__ == "__main__":
    main()
