
import baostock as bs
import pandas as pd
import datetime
import time
import concurrent.futures
import os
import multiprocessing
import random

# Configuration
MD_FILE = "temp/baostock_fetch_test_v3.md"
MAX_WORKERS = 16 
TARGET_STOCKS = 500
DAYS_TO_FETCH = 10

# ============================================================
# NOTE: This script MUST use ProcessPoolExecutor, NOT ThreadPool.
#       Each child process has its own memory, so IS_LOGGED_IN
#       is correctly isolated. ThreadPool would share state incorrectly.
# ============================================================

# Global state per process (isolated in each subprocess)
IS_LOGGED_IN = False

def force_relogin(retries=3):
    global IS_LOGGED_IN
    
    try:
        bs.logout()
    except:
        pass
        
    for i in range(retries):
        try:
            time.sleep(random.uniform(0.1, 1.0) * (i + 1))
            lg = bs.login()
            if lg.error_code == '0':
                IS_LOGGED_IN = True
                return True
            else:
                print(f"[PID {os.getpid()}] Login failed (Attempt {i+1}): {lg.error_msg}")
        except Exception as e:
            print(f"[PID {os.getpid()}] Login exception: {e}")
            
    IS_LOGGED_IN = False
    return False

def ensure_login():
    global IS_LOGGED_IN
    if not IS_LOGGED_IN:
        return force_relogin()
    return True

def fetch_task_safe(code):
    """
    Returns a tuple: (code, data_list, status)
    Status can be: "OK", "NO_DATA", "ERROR:<reason>", "LOGIN_FAILED", "MAX_RETRIES"
    """
    global IS_LOGGED_IN
    
    max_retries = 3
    last_error = ""
    
    for attempt in range(max_retries):
        try:
            if not ensure_login():
                if attempt == max_retries - 1:
                    return (code, [], "LOGIN_FAILED")
                continue

            end = datetime.date.today().strftime("%Y-%m-%d")
            start = (datetime.date.today() - datetime.timedelta(days=DAYS_TO_FETCH * 2)).strftime("%Y-%m-%d")
            
            rs = bs.query_history_k_data_plus(
                code,
                "date,code,open,high,low,close,volume,amount",
                start_date=start,
                end_date=end,
                frequency="d",
                adjustflag="2"
            )
            
            # Not logged in -> retry
            if rs.error_code == '10001001':
                IS_LOGGED_IN = False
                last_error = "NOT_LOGGED_IN"
                continue
            
            # Other API error
            if rs.error_code != '0':
                last_error = f"API_ERROR:{rs.error_code}:{rs.error_msg}"
                continue
                
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            
            # Distinguish success with data vs success with no data
            if len(data_list) == 0:
                return (code, [], "NO_DATA")
            else:
                return (code, data_list, "OK")
            
        except Exception as e:
            err_str = str(e)
            last_error = f"EXCEPTION:{err_str}"
            if "socket" in err_str.lower() or "connection" in err_str.lower():
                IS_LOGGED_IN = False
                time.sleep(1)
    
    return (code, [], f"MAX_RETRIES:{last_error}")


def main():
    # 1. Get Stock List
    lg = bs.login()
    if lg.error_code != '0':
        print(f"FATAL: Cannot login to Baostock: {lg.error_msg}")
        return
        
    rs = bs.query_stock_basic()
    if rs.error_code != '0':
        print(f"FATAL: query_stock_basic failed: {rs.error_code} {rs.error_msg}")
        bs.logout()
        return
        
    stock_list = []
    while rs.next():
        row = rs.get_row_data()
        if row:
            stock_list.append(row[0])
    bs.logout()
    
    print(f"[DEBUG] query_stock_basic returned {len(stock_list)} codes.")
    
    # Filter
    all_codes = stock_list
    stock_list = [c for c in stock_list if c.startswith('sh.') or c.startswith('sz.')]
    
    print(f"[DEBUG] After prefix filter: {len(stock_list)} codes.")
    
    if not stock_list:
        print(f"Warning: No stocks found with prefix sh/sz. Using top 200 raw.")
        stock_list = all_codes[:200]
    else:
        stock_list = stock_list[:TARGET_STOCKS]
        
    print(f"Benchmarking v3 with {len(stock_list)} stocks using {MAX_WORKERS} processes...")

    
    start_time = time.time()
    
    # Result tracking
    success_data = []  # List of rows
    success_codes = []
    no_data_codes = []
    failed_codes = []  # (code, reason)
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_task_safe, code): code for code in stock_list}
        
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            code, rows, status = future.result()
            
            if status == "OK":
                success_data.extend(rows)
                success_codes.append(code)
            elif status == "NO_DATA":
                no_data_codes.append(code)
            else:
                failed_codes.append((code, status))
                
            completed += 1
            if completed % 50 == 0:
                print(f"Progress: {completed}/{len(stock_list)}")
                
    duration = time.time() - start_time
    speed = len(stock_list) / duration if duration > 0 else 0
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"Total Stocks: {len(stock_list)}")
    print(f"  ✅ Success (with data): {len(success_codes)}")
    print(f"  ⚠️ Success (no data): {len(no_data_codes)}")
    print(f"  ❌ Failed: {len(failed_codes)}")
    print(f"Total Rows: {len(success_data)}")
    print(f"Time: {duration:.2f}s, Speed: {speed:.2f} stocks/s")
    
    # Write Report
    with open(MD_FILE, "w", encoding='utf-8') as f:
        f.write(f"# Baostock Efficient Fetch Test V3 (Reviewed)\n\n")
        f.write(f"- **Timestamp**: {datetime.datetime.now()}\n")
        f.write(f"- **Workers**: {MAX_WORKERS}\n")
        f.write(f"- **Stocks Requested**: {len(stock_list)}\n")
        f.write(f"- **Time**: {duration:.2f}s\n")
        f.write(f"- **Speed**: {speed:.2f} stocks/s\n\n")
        
        f.write("## Data Completeness\n\n")
        f.write(f"| Category | Count |\n")
        f.write(f"|---|---|\n")
        f.write(f"| ✅ Success (with data) | {len(success_codes)} |\n")
        f.write(f"| ⚠️ No Data (possibly suspended/new) | {len(no_data_codes)} |\n")
        f.write(f"| ❌ Failed | {len(failed_codes)} |\n")
        f.write(f"| **Total Rows Fetched** | {len(success_data)} |\n\n")
        
        if failed_codes:
            f.write("## Failed Codes\n\n")
            f.write("| Code | Reason |\n")
            f.write("|---|---|\n")
            for code, reason in failed_codes:
                f.write(f"| {code} | {reason} |\n")
            f.write("\n")
            
        if no_data_codes:
            f.write("## No Data Codes (Sample)\n\n")
            f.write(f"`{', '.join(no_data_codes[:20])}`\n\n")
        
        f.write("## Sample Data (Top 100 Rows)\n\n")
        f.write("| Date | Code | Open | High | Low | Close | Volume | Amount |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for row in success_data[:100]:
            f.write(f"| {' | '.join(row)} |\n")
             
    print(f"\nReport saved to {MD_FILE}")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

