
import baostock as bs
import pandas as pd
import requests
import datetime
import time
import concurrent.futures
import traceback
import random
import os
import sys
import multiprocessing

try:
    from .limit_calc import LimitCalculator
except (ImportError, ValueError):
    from limit_calc import LimitCalculator

# 使用统一配置加载器
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config_loader import CK_HOST, CK_AUTH, get_etl_config, get_maintained_indices

# 获取 ETL 配置
_etl_cfg = get_etl_config()
MAX_WORKERS = _etl_cfg['max_workers']

# 获取维护的指数列表
MAINTAINED_INDICES = get_maintained_indices()


START_DATE_DEFAULT = "2021-01-01"
END_DATE_DEFAULT = datetime.date.today().strftime("%Y-%m-%d")

# ============================================================
# NOTE: This ETL MUST use ProcessPoolExecutor for Baostock.
#       Each child process has its own memory, so IS_LOGGED_IN
#       is correctly isolated. ThreadPool would share state incorrectly.
# ============================================================

# Global state per process (isolated in each subprocess)
IS_LOGGED_IN = False

# 注册子进程退出清理函数
import atexit

def _cleanup_baostock():
    """确保 Baostock 会话在进程退出时关闭"""
    global IS_LOGGED_IN
    if IS_LOGGED_IN:
        try:
            bs.logout()
        except:
            pass
        IS_LOGGED_IN = False

atexit.register(_cleanup_baostock)

def force_relogin(retries=3):
    """Force logout/login with exponential backoff and jitter."""
    global IS_LOGGED_IN
    
    try:
        bs.logout()
    except:
        pass
        
    for i in range(retries):
        try:
            # Random jitter to prevent thundering herd
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
    """Ensure we are logged in, attempt re-login if not."""
    global IS_LOGGED_IN
    if not IS_LOGGED_IN:
        return force_relogin()
    return True

# --- Helper Classes ---

class BaostockWorker:
    """Robust baostock session wrapper with auto-recovery."""
    
    @staticmethod
    def fetch_history(code, start_date, end_date):
        """
        Fetch K-line data with robust retry logic.
        Returns: (DataFrame or None, error_message or None)
        """
        global IS_LOGGED_IN
        
        fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST"
        max_retries = 3
        last_error = ""
        
        for attempt in range(max_retries):
            try:
                if not ensure_login():
                    if attempt == max_retries - 1:
                        return None, "LOGIN_FAILED after retries"
                    continue
                
                rs = bs.query_history_k_data_plus(
                    code, fields,
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",
                    adjustflag="3"
                )
                
                # Handle specific error codes
                if rs.error_code == '10001001':
                    # Not logged in - force re-login
                    IS_LOGGED_IN = False
                    last_error = "NOT_LOGGED_IN"
                    continue
                
                if rs.error_code != '0':
                    last_error = f"API Error {rs.error_code}: {rs.error_msg}"
                    continue
                
                # Success - parse data
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                    
                if not data_list:
                    return pd.DataFrame(), None
                    
                df = pd.DataFrame(data_list, columns=fields.split(','))
                return df, None
                
            except Exception as e:
                err_str = str(e)
                last_error = f"Exception: {err_str}"
                
                # Socket/connection errors - force reset
                if "socket" in err_str.lower() or "connection" in err_str.lower():
                    IS_LOGGED_IN = False
                    time.sleep(1)  # Cool down
        
        return None, f"MAX_RETRIES: {last_error}"



def get_securities_map():
    """Returns list of dicts: [{'code':..., 'type':...}, ...]"""
    
    # 1. Get Stocks from DB
    sql = "SELECT code, type, ipo_date, out_date FROM stock_data.securities_info"
    res = []
    
    try:
        r = requests.post(CK_HOST, params={'query': sql}, auth=CK_AUTH)
        if r.status_code == 200:
            lines = [line.strip().split('\t') for line in r.text.strip().split('\n') if line]
            # Schema: code, type, ipo, out
            for l in lines:
                code = l[0]
                typ = int(l[1])
                
                # Only include Stocks (Type 1) here. Indices handled separately below.
                if typ == 1:
                    res.append({
                        'code': code,
                        'type': 1,
                        'ipo': l[2],
                        'out': l[3]
                    })
    except Exception as e:
        print(f"Failed to fetch securities: {e}")
        return []
        
    # 2. Add Maintained Indices from Config
    for idx_code in MAINTAINED_INDICES:
        res.append({
            'code': idx_code,
            'type': 2, # Index
            'ipo': '1990-01-01', # Default start
            'out': '2999-12-31'
        })
        
    return res




def bulk_insert_ck(table, values):
    """Bulk insert VALUES into ClickHouse table."""
    if not values:
        return
    
    sql = f"INSERT INTO {table} VALUES {','.join(values)}"
    try:
        r = requests.post(CK_HOST, data=sql, auth=CK_AUTH)
        if r.status_code != 200:
            print(f"ClickHouse insert error ({table}): {r.text[:200]}")
        else:
            print(f"Inserted {len(values)} rows into {table}")
    except Exception as e:
        print(f"ClickHouse exception ({table}): {e}")


def get_max_dates():

    """query max(date) for each code to determine start point"""
    # Unions stocks and indexes
    sql = """
    SELECT code, toString(max(date)) as last_dt FROM stock_data.stock_kline_day GROUP BY code
    UNION ALL
    SELECT code, toString(max(date)) as last_dt FROM stock_data.index_kline_day GROUP BY code
    """
    try:
        r = requests.post(CK_HOST, params={'query': sql}, auth=CK_AUTH)
        if r.status_code == 200:
            lines = [line.strip().split('\t') for line in r.text.strip().split('\n') if line]
            return {l[0]: l[1] for l in lines}
    except Exception as e:
        print(f"Failed to fetch max dates: {e}")
    return {}

def worker_task(stock_info, last_known_date=None):
    code = stock_info['code']
    typ = stock_info['type']
    ipo = stock_info['ipo']
    
    # Determine Start Date
    if last_known_date:
        # Incremental: Start from next day
        try:
            d_obj = datetime.datetime.strptime(last_known_date, "%Y-%m-%d")
            start_date_obj = d_obj + datetime.timedelta(days=1)
            start_date = start_date_obj.strftime("%Y-%m-%d")
        except:
            start_date = START_DATE_DEFAULT
    else:
        # Full / Init
        start_date = ipo if ipo > START_DATE_DEFAULT else START_DATE_DEFAULT
        
    # Check Delisting
    out_date = stock_info.get('out', '2999-12-31')
    if out_date == '': out_date = '2999-12-31' # Handle empty string
    
    end_date = END_DATE_DEFAULT

    if start_date > end_date:
        return {'code': code, 'status': 'skip', 'msg': 'Already up to date'}
        
    if start_date > out_date:
        return {'code': code, 'status': 'skip', 'msg': f'Delisted on {out_date}'}

    
    # Use static method (no instance needed)
    df, err = BaostockWorker.fetch_history(code, start_date, end_date)

    
    if err:
        return {'code': code, 'status': 'error', 'msg': err}
    
    if df.empty:
        return {'code': code, 'status': 'empty', 'msg': 'No data'}

    # --- Processing (Same as before) ---
    try:
        # Typos conversions
        numeric_cols = ['open','high','low','close','preclose','volume','amount','turn','pctChg']
        for c in numeric_cols:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
        df['tradestatus'] = pd.to_numeric(df['tradestatus'], errors='coerce').fillna(1).astype(int)
        df['isST'] = pd.to_numeric(df['isST'], errors='coerce').fillna(0).astype(int)
        df['adjustflag'] = 3
        
        table_name = "stock_data.stock_kline_day" if typ == 1 else "stock_data.index_kline_day"
        
        if typ == 1:
            df = LimitCalculator.calculate_limits(df)
            
            def get_status(row):
                c = row['close']
                h = row['high']
                up = row['limit_up_price']
                down = row['limit_down_price']
                if c >= up: return 1
                if c <= down: return 2
                if h >= up and c < up: return 3
                return 0
                
            df['limit_status'] = df.apply(get_status, axis=1)

        out_rows = []
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        value_list = []
        
        for _, row in df.iterrows():
            d = row['date']
            o = row['open']
            h = row['high']
            l = row['low']
            c = row['close']
            pre = row['preclose']
            v = int(row['volume'])
            a = row['amount']
            pc = row['pctChg']
            
            if typ == 1:
                t = row['turn']
                ts = row['tradestatus']
                st_flag = int(row['isST'])
                af = 3
                lu = row['limit_up_price']
                ld = row['limit_down_price']
                ls = row['limit_status']
                val = f"('{code}', '{d}', {o}, {h}, {l}, {c}, {pre}, {v}, {a}, {t}, {pc}, {ts}, {st_flag}, {af}, {lu}, {ld}, {ls}, '{now_str}')"
            else:
                val = f"('{code}', '{d}', {o}, {h}, {l}, {c}, {pre}, {v}, {a}, {pc}, '{now_str}')"
                
            value_list.append(val)
            
        return {'code': code, 'status': 'success', 'table': table_name, 'values': value_list}
            
    except Exception as e:
        traceback.print_exc()
        return {'code': code, 'status': 'error', 'msg': str(e)}

# Re-use bulk_insert_ck from original code (it's fine)

def run_etl(mode='incremental'):
    """
    Main Logic for External Call (UI).
    mode: 'incremental' (default) or 'full' (ignore existing data)
    """
    try:
        print("Initializing Kline Loader...")
        # NOTE: Do NOT login here - each subprocess will manage its own session
        
        securities = get_securities_map()
        if not securities:
            return False, "No securities found. Populate securities_info first."
            
        existing_dates = {}
        if mode == 'incremental':
            print("Fetching existing max dates for incremental update...")
            existing_dates = get_max_dates()
        
        print(f"Loaded {len(securities)} securities. Mode={mode}. Workers={MAX_WORKERS}")
        
        buffer_stock = []
        buffer_index = []
        BUFFER_LIMIT = 20000
        
        count_all = 0
        count_success = 0
        count_skip = 0
        count_error = 0
        
        # Use ProcessPoolExecutor for Baostock (each process has isolated session)
        executor = concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS)
        try:
            # Prepare tasks
            future_map = {}
            for s in securities:
                last_dt = existing_dates.get(s['code'])
                future = executor.submit(worker_task, s, last_dt)
                future_map[future] = s['code']

            
            total = len(securities)
            
            # Progress Wrapper for UI? 
            # Currently just blocking call returning final status
            
            for i, future in enumerate(concurrent.futures.as_completed(future_map)):
                res = future.result()
                count_all += 1
                
                if res['status'] == 'success':
                    count_success += 1
                    if 'stock_kline' in res['table']:
                        buffer_stock.extend(res['values'])
                    else:
                        buffer_index.extend(res['values'])
                elif res['status'] == 'skip':
                    count_skip += 1
                elif res['status'] == 'error':
                    count_error += 1

                    
                # Flush
                if len(buffer_stock) >= BUFFER_LIMIT:
                    bulk_insert_ck("stock_data.stock_kline_day", buffer_stock)
                    buffer_stock = []
                if len(buffer_index) >= BUFFER_LIMIT:
                    bulk_insert_ck("stock_data.index_kline_day", buffer_index)
                    buffer_index = []
                    
                if (i + 1) % 100 == 0 or (i + 1) == total:
                    print(f"Processed {i+1}/{total}...")
        finally:
            # 强制关闭 executor，不等待子进程
            print("Shutting down executor...")
            executor.shutdown(wait=False, cancel_futures=True)

        print("All tasks completed. performing final flush...")
        
        # Final flush
        if buffer_stock:
            print(f"Flushing final {len(buffer_stock)} stock records...")
            bulk_insert_ck("stock_data.stock_kline_day", buffer_stock)
        if buffer_index:
            print(f"Flushing final {len(buffer_index)} index records...")
            bulk_insert_ck("stock_data.index_kline_day", buffer_index)
            
        print("Final flush done. Cleaning up...")
        
        # 强制终止可能残留的子进程
        import gc
        gc.collect()
        
        print("ETL completed successfully.")
        return True, f"ETL Complete: {count_success} updated, {count_skip} skipped, {count_error} failed out of {count_all} total."


        
    except Exception as e:
        traceback.print_exc()
        return False, f"ETL Fatal Error: {e}"

def main():
    multiprocessing.freeze_support()
    success, msg = run_etl(mode='incremental')
    print(msg)

if __name__ == "__main__":
    main()


