
import baostock as bs
import pandas as pd
import requests
import datetime
from io import StringIO
import re
import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from config_loader import CK_HOST, CK_AUTH

CUTOFF_DATE = "2021-01-01"

def get_ck_min_dates():
    print("Fetching CK stats...")
    sql = "SELECT code, toString(min(date)) as min_date, toString(max(date)) as max_date FROM stock_data.stock_kline_day GROUP BY code FORMAT CSVWithNames"
    r = requests.post(CK_HOST, params={'query': sql}, auth=CK_AUTH)
    return pd.read_csv(StringIO(r.text))

def analyze_start_dates():
    # 1. Get Target List
    bs.login()
    print("Fetching target list from Baostock...")
    rs = bs.query_all_stock(day="2026-01-21")
    target_data = []
    while rs.next():
        target_data.append(rs.get_row_data()) # code, tradeStatus, name
    
    # Filter A-Share
    def is_a_stock(code):
        if code.startswith('sh.60') or code.startswith('sh.68'): return True
        if code.startswith('sz.00') or code.startswith('sz.30'): return True
        if code.startswith('bj.4') or code.startswith('bj.8'): return True
        return False
        
    target_stocks = [x[0] for x in target_data if is_a_stock(x[0])]
    print(f"Target Stocks: {len(target_stocks)}")
    
    # 2. Get CK Stats
    df_ck = get_ck_min_dates()
    df_ck.set_index('code', inplace=True)
    
    # 3. Verify
    print("Verifying start dates logic...")
    
    mismatch_count = 0
    missing_count = 0
    checked_count = 0
    
    details = []
    
    # Batch processing? No, Baostock doesn't support batch query basic info efficiently for start date.
    # But we can assume start date = IPO date or First Trading Date.
    # query_stock_basic() gives ipoDate.
    
    # Getting IPO dates is faster than querying history for every stock
    # Note: query_stock_basic returns everything. We filter locally.
    rs_basic = bs.query_stock_basic()
    basic_data = []
    while rs_basic.next():
        basic_data.append(rs_basic.get_row_data())
    
    # basic: code, code_name, ipoDate, outDate, type, status
    df_basic = pd.DataFrame(basic_data, columns=['code', 'code_name', 'ipoDate', 'outDate', 'type', 'status'])
    df_basic.set_index('code', inplace=True)
    
    cutoff_dt = pd.to_datetime(CUTOFF_DATE)
    
    for code in target_stocks:
        checked_count += 1
        if code not in df_ck.index:
            missing_count += 1
            details.append({'code': code, 'status': 'MISSING_IN_CK', 'exp': '?', 'act': 'None'})
            continue
            
        act_min_str = df_ck.loc[code, 'min_date']
        act_min = pd.to_datetime(act_min_str)
        
        # Determine Expected
        # Method A: Use IPO Date
        if code in df_basic.index:
            ipo_str = df_basic.loc[code, 'ipoDate']
            # Some IPO dates are empty?
            if not ipo_str:
                exp_min = cutoff_dt # Fallback
            else:
                ipo_dt = pd.to_datetime(ipo_str)
                exp_min = max(ipo_dt, cutoff_dt)
        else:
            # If not in basic, fetch history (Slow path)
            # Actually if it is in target_stocks (from query_all_stock), it must exist.
            # But query_stock_basic might be stale?
            exp_min = cutoff_dt
            
        # Tolerance: Allow actual date to be slightly later than expected (e.g. suspension on Jan 1)
        # Tolerance: 15 days
        diff = (act_min - exp_min).days
        
        # Check logic:
        # If IPO < 2021-01-01: Expect 2021-01-01 (approx)
        # If IPO > 2021-01-01: Expect IPO (approx)
        
        status = "OK"
        if act_min < exp_min: 
            # This is actually weird. CK has data BEFORE expected? 
            # Unless we imported data from 1990 by mistake?
            # Or data cleaning issue?
            status = "EARLIER_THAN_EXPECTED"
        elif diff > 20: 
            # Too late. E.g. expected 2021-01-01, but act 2022-03.
            status = "LATE_START"
            
        if status != "OK":
            mismatch_count += 1
            details.append({
                'code': code, 
                'status': status, 
                'exp': exp_min.date(), 
                'act': act_min.date(), 
                'diff_days': diff
            })
            
    print(f"\nChecked: {checked_count}")
    print(f"Missing in CK: {missing_count}")
    print(f"Date Mismatch: {mismatch_count}")
    
    if details:
        print(f"\nTop 20 Mismatches:")
        print(pd.DataFrame(details).head(20).to_markdown())
        
        # Save full report
        pd.DataFrame(details).to_csv("verification_report_dates.csv", index=False)
        print("Full report saved to verification_report_dates.csv")

    bs.logout()

if __name__ == "__main__":
    analyze_start_dates()
