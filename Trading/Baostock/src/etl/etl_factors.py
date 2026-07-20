
import baostock as bs
import pandas as pd
import requests
import datetime
import os
import sys
import time
import random
import concurrent.futures
import multiprocessing

# 使用统一配置加载器
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config_loader import CK_HOST, CK_AUTH, get_etl_config

# 获取 ETL 配置
_etl_cfg = get_etl_config()
MAX_WORKERS = _etl_cfg['max_workers']

# ============================================================
# NOTE: Uses ProcessPoolExecutor for parallel Baostock fetching.
# ============================================================

IS_LOGGED_IN = False

def force_relogin(retries=3):
    global IS_LOGGED_IN
    try:
        bs.logout()
    except:
        pass
    for i in range(retries):
        try:
            time.sleep(random.uniform(0.1, 0.5) * (i + 1))
            lg = bs.login()
            if lg.error_code == '0':
                IS_LOGGED_IN = True
                return True
        except:
            pass
    IS_LOGGED_IN = False
    return False

def ensure_login():
    global IS_LOGGED_IN
    if not IS_LOGGED_IN:
        return force_relogin()
    return True

def fetch_factor_for_code(args):
    """
    Worker function: fetch adjust factors for one stock.
    args = (code, last_known_date)  
    Returns: (code, rows_list, status)
    """
    global IS_LOGGED_IN
    code, last_date = args
    
    # Determine start date
    if last_date:
        # Incremental: from next day
        try:
            d_obj = datetime.datetime.strptime(last_date, "%Y-%m-%d")
            start_date = (d_obj + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        except:
            start_date = "1990-01-01"
    else:
        start_date = "1990-01-01"
    
    end_date = datetime.date.today().strftime("%Y-%m-%d")
    
    # Skip if already up to date
    if start_date > end_date:
        return (code, [], "SKIP")
    
    for attempt in range(3):
        try:
            if not ensure_login():
                if attempt == 2:
                    return (code, [], "LOGIN_FAILED")
                continue
            
            rs = bs.query_adjust_factor(code=code, start_date=start_date, end_date=end_date)
            
            if rs.error_code == '10001001':
                IS_LOGGED_IN = False
                continue
                
            if rs.error_code != '0':
                continue
            
            rows = []
            while rs.next():
                row = rs.get_row_data()
                c = row[0]
                d = row[1]
                f = row[2] if row[2] else '0.0'
                b = row[3] if row[3] else '0.0'
                rows.append(f"('{c}', '{d}', {f}, {b})")
            
            if not rows:
                return (code, [], "NO_NEW_DATA")
            return (code, rows, "OK")
            
        except Exception as e:
            err_str = str(e).lower()
            if "socket" in err_str or "connection" in err_str:
                IS_LOGGED_IN = False
                time.sleep(0.5)
    
    return (code, [], "MAX_RETRIES")


def get_target_stocks():
    """Get all stock codes from ClickHouse."""
    sql = "SELECT code FROM stock_data.securities_info WHERE type=1"
    try:
        r = requests.post(CK_HOST, params={'query': sql}, auth=CK_AUTH)
        if r.status_code == 200:
            return [line.strip() for line in r.text.strip().split('\n') if line]
    except:
        pass
    return []


def get_existing_max_dates():
    """Get max dividOperateDate per code from ClickHouse."""
    sql = "SELECT code, toString(max(dividOperateDate)) FROM stock_data.adjust_factor GROUP BY code"
    try:
        r = requests.post(CK_HOST, params={'query': sql}, auth=CK_AUTH)
        if r.status_code == 200:
            lines = [line.strip().split('\t') for line in r.text.strip().split('\n') if line]
            return {l[0]: l[1] for l in lines if len(l) == 2}
    except:
        pass
    return {}


def bulk_insert_factors(rows):
    """Insert rows into ClickHouse."""
    if not rows:
        return
    sql = f"INSERT INTO stock_data.adjust_factor (code, dividOperateDate, foreAdjustFactor, backAdjustFactor) VALUES {','.join(rows)}"
    try:
        r = requests.post(CK_HOST, data=sql, auth=CK_AUTH)
        if r.status_code != 200:
            print(f"Insert error: {r.text[:200]}")
        else:
            print(f"Inserted {len(rows)} factor records")
    except Exception as e:
        print(f"Insert exception: {e}")


def run_etl(mode='incremental'):
    """
    Main ETL entry point.
    mode: 'incremental' (default) or 'full'
    """
    try:
        print("Starting Factor ETL...")
        
        codes = get_target_stocks()
        if not codes:
            return False, "No stock codes found. Run Securities Sync first."
        
        # Get existing max dates for incremental
        existing_dates = {}
        if mode == 'incremental':
            print("Fetching existing max dates for incremental update...")
            existing_dates = get_existing_max_dates()
            print(f"Found {len(existing_dates)} codes with existing factor data")
        else:
            # Full mode: truncate first
            print("Full mode: truncating adjust_factor table...")
            requests.post(CK_HOST, data="TRUNCATE TABLE stock_data.adjust_factor", auth=CK_AUTH)
        
        print(f"Processing {len(codes)} stocks with {MAX_WORKERS} workers...")
        
        # Prepare args
        args_list = [(code, existing_dates.get(code)) for code in codes]
        
        all_rows = []
        count_ok = 0
        count_skip = 0
        count_no_new = 0
        count_error = 0
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_factor_for_code, arg): arg[0] for arg in args_list}
            
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                code, rows, status = future.result()
                
                if status == "OK":
                    count_ok += 1
                    all_rows.extend(rows)
                elif status == "SKIP":
                    count_skip += 1
                elif status == "NO_NEW_DATA":
                    count_no_new += 1
                else:
                    count_error += 1
                
                # Batch insert
                if len(all_rows) >= 10000:
                    bulk_insert_factors(all_rows)
                    all_rows = []
                
                if (i + 1) % 200 == 0:
                    print(f"Progress: {i+1}/{len(codes)}")
        
        # Final flush
        if all_rows:
            bulk_insert_factors(all_rows)
        
        msg = f"Factor ETL done: {count_ok} updated, {count_skip} skipped (up-to-date), {count_no_new} no new data, {count_error} failed"
        print(msg)
        return True, msg
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Factor ETL Error: {e}"


def main():
    multiprocessing.freeze_support()
    success, msg = run_etl(mode='incremental')
    print(msg)


if __name__ == "__main__":
    main()
