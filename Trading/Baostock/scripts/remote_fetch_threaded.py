"""
remote_fetch_threaded.py - threaded baostock fetcher using a single shared connection.

Why threading (not multiprocessing):
  baostock's Python SDK is single-session, single-socket.
  Multiple processes each bs.login() -> multiple concurrent connections -> throttled/broken.
  Multiple threads sharing the same bs connection -> OK because baostock SDK is
  designed for single-threaded use, but Python's GIL serializes our access,
  so requests go out one-at-a-time through the same socket.
  
  Caveat: baostock's SDK may not actually be thread-safe internally. If you see
  broken pipes, fall back to remote_fetch_serial.py (pure serial).
"""

import argparse
import datetime
import os
import sys
import time
import gzip
import threading
from concurrent.futures import ThreadPoolExecutor
from io import StringIO

import pandas as pd
import baostock as bs

# Reuse helpers from serial version
MAINTAINED_INDICES = [
    "sh.000001", "sh.000016", "sh.000300", "sh.000905", "sh.000852",
    "sz.000510", "sz.399006", "sz.000688", "sz.399001",
]
KLINE_FIELDS = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST"
FACTOR_FIELDS = "code,dividOperateDate,foreAdjustFactor,backAdjustFactor"

# Serialize all bs calls (single-socket, single thread for actual IO)
_bs_lock = threading.Lock()
_logged_in = False
_log_lock = threading.Lock()

def _log(msg):
    with _log_lock:
        print(msg, flush=True)

def ensure_login():
    global _logged_in
    with _bs_lock:
        for attempt in range(5):
            try:
                bs.logout()
            except Exception:
                pass
            if attempt > 0:
                wait = 20 * attempt
                _log(f"[login] backoff {wait}s...")
                time.sleep(wait)
            try:
                lg = bs.login()
                if lg.error_code == '0':
                    _logged_in = True
                    _log(f"[login] OK (attempt {attempt+1})")
                    return True
                _log(f"[login] attempt {attempt+1} failed: {lg.error_code} {lg.error_msg}")
            except Exception as e:
                _log(f"[login] attempt {attempt+1} exc: {e}")
        _logged_in = False
        return False

def _do_kline(code, start, end):
    """Must be called with _bs_lock held."""
    rs = bs.query_history_k_data_plus(code, KLINE_FIELDS, start_date=start, end_date=end, frequency="d", adjustflag="3")
    if rs.error_code == '10001001':
        return None, "RELOGIN"
    if rs.error_code != '0':
        return None, f"API_{rs.error_code}"
    data = []
    while rs.next():
        data.append(rs.get_row_data())
    if not data:
        return pd.DataFrame(), None
    return pd.DataFrame(data, columns=KLINE_FIELDS.split(',')), None

def fetch_kline(code, start, end):
    for attempt in range(3):
        with _bs_lock:
            df, err = _do_kline(code, start, end)
            if err == "RELOGIN":
                # need to re-login (still holding lock)
                if not ensure_login():
                    return None, "LOGIN_FAILED"
                continue
        return df, err
    return None, "MAX_RETRIES"

def _do_factor(code, start, end):
    rs = bs.query_adjust_factor(code, start_date=start, end_date=end)
    if rs.error_code == '10001001':
        return None, "RELOGIN"
    if rs.error_code != '0':
        return None, f"API_{rs.error_code}"
    data = []
    while rs.next():
        data.append(rs.get_row_data())
    if not data:
        return pd.DataFrame(), None
    return pd.DataFrame(data, columns=FACTOR_FIELDS.split(',')), None

def fetch_factors(code, start, end):
    for attempt in range(3):
        with _bs_lock:
            df, err = _do_factor(code, start, end)
            if err == "RELOGIN":
                if not ensure_login():
                    return None, "LOGIN_FAILED"
                continue
        return df, err
    return None, "MAX_RETRIES"

def process_stock_kline(df):
    if df.empty:
        return df
    for c in ['open','high','low','close','preclose','volume','amount','turn','pctChg']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    df['tradestatus'] = pd.to_numeric(df['tradestatus'], errors='coerce').fillna(1).astype(int)
    df['isST'] = pd.to_numeric(df['isST'], errors='coerce').fillna(0).astype(int)
    df['adjustflag'] = 3
    df = df.copy()
    df['preclose_calc'] = df.groupby('code', group_keys=False)['close'].apply(lambda s: s.shift(1))
    df['preclose_calc'] = df['preclose_calc'].fillna(df['close'])
    is_st = df['isST'].fillna(0).astype(int) == 1
    rate = pd.Series(0.10, index=df.index)
    rate[is_st] = 0.05
    df['limit_up_price'] = (df['preclose_calc'] * (1 + rate)).apply(lambda x: round(float(x)+1e-9, 2))
    df['limit_down_price'] = (df['preclose_calc'] * (1 - rate)).apply(lambda x: round(float(x)+1e-9, 2))
    df = df.drop(columns=['preclose_calc'])
    def _status(row):
        c, h, up, down = row['close'], row['high'], row['limit_up_price'], row['limit_down_price']
        if c >= up: return 1
        if c <= down: return 2
        if h >= up and c < up: return 3
        return 0
    df['limit_status'] = df.apply(_status, axis=1)
    return df

def process_index_kline(df):
    if df.empty:
        return df
    for c in ['open','high','low','close','preclose','volume','amount','pctChg']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    return df

def process_factor(df):
    if df.empty:
        return df
    df['foreAdjustFactor'] = pd.to_numeric(df['foreAdjustFactor'], errors='coerce')
    df['backAdjustFactor'] = pd.to_numeric(df['backAdjustFactor'], errors='coerce')
    return df

def write_gz_csv(df, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    buf = StringIO()
    df.to_csv(buf, index=False)
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        f.write(buf.getvalue())
    _log(f"  wrote {path}  rows={len(df)}  size={os.path.getsize(path)/1024:.1f}KB")

def get_all_stock_codes():
    with _bs_lock:
        today = datetime.date.today().strftime("%Y-%m-%d")
        rs = bs.query_all_stock(day=today)
        if rs.error_code != '0':
            return []
        codes = []
        while rs.error_code == '0' and rs.next():
            c = rs.get_row_data()[0]
            if c.startswith(('sh.', 'sz.')):
                codes.append(c)
        return codes

def fetch_stock_basic():
    with _bs_lock:
        rs = bs.query_stock_basic()
        if rs.error_code != '0':
            return None
        data = []
        while rs.error_code == '0' and rs.next():
            data.append(rs.get_row_data())
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data, columns=rs.fields)

def thread_fetch(worker_fn, codes, start, end, label, n_threads=4):
    """Use ThreadPoolExecutor; bs calls serialized via _bs_lock inside worker_fn."""
    results = []
    err_count = 0
    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=n_threads) as ex:
        futures = {ex.submit(worker_fn, c, start, end): c for c in codes}
        for fut in futures:
            done += 1
            try:
                kind, code, df, err = fut.result()
                if err:
                    err_count += 1
                    if err_count <= 3:
                        _log(f"  [{label}][{code}] err: {err}")
                else:
                    results.append(df)
            except Exception as e:
                err_count += 1
                if err_count <= 3:
                    _log(f"  [{label}] exc: {e}")
            if done % 200 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed
                eta = (len(codes) - done) / rate
                _log(f"  [{label}] {done}/{len(codes)} err={err_count} {rate:.1f}/s ETA {eta:.0f}s")
    _log(f"  [{label}] done: ok={len(results)} err={err_count} total={done} time={time.time()-t0:.1f}s")
    return results, err_count

def stock_kline_wrapper(code, start, end):
    df, err = fetch_kline(code, start, end)
    if err or df is None or df.empty:
        return ('stock', code, None, err)
    return ('stock', code, process_stock_kline(df), None)

def factor_wrapper(code, start, end):
    df, err = fetch_factors(code, start, end)
    if err or df is None or df.empty:
        return ('factor', code, None, err)
    return ('factor', code, process_factor(df), None)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--start-date', required=True)
    p.add_argument('--end-date', default=datetime.date.today().strftime("%Y-%m-%d"))
    p.add_argument('--out-dir', required=True)
    p.add_argument('--buffer-days', type=int, default=3)
    p.add_argument('--skip-securities', action='store_true')
    p.add_argument('--threads', type=int, default=4)
    args = p.parse_args()

    start = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()
    buf_start = (start - datetime.timedelta(days=args.buffer_days)).strftime("%Y-%m-%d")
    os.makedirs(args.out_dir, exist_ok=True)

    print("=" * 60, flush=True)
    print(f"Remote baostock fetch (THREADED, single shared socket)", flush=True)
    print(f"  start_date:  {args.start_date}  (buffered: {buf_start})", flush=True)
    print(f"  end_date:    {args.end_date}", flush=True)
    print(f"  out_dir:     {args.out_dir}", flush=True)
    print(f"  threads:     {args.threads} (all share 1 bs connection)", flush=True)
    print("=" * 60, flush=True)

    if not ensure_login():
        print("FATAL: baostock login failed", flush=True)
        sys.exit(1)

    print("\n[0/4] Discovering A-share codes...", flush=True)
    codes = get_all_stock_codes()
    print(f"  got {len(codes)} active A-share codes", flush=True)

    # 1) Stock K-line
    print(f"\n[1/4] Fetching stock K-line (threaded x{args.threads}, {len(codes)} codes)...", flush=True)
    stock_dfs, _ = thread_fetch(stock_kline_wrapper, codes, buf_start, args.end_date, 'stock', args.threads)
    if stock_dfs:
        all_stocks = pd.concat(stock_dfs, ignore_index=True)
        write_gz_csv(all_stocks, os.path.join(args.out_dir, "kline_stocks.csv.gz"))
        print(f"[1/4] total stock rows: {len(all_stocks)}", flush=True)
    else:
        print("[1/4] no stock data", flush=True)

    # 2) Index K-line
    print(f"\n[2/4] Fetching index K-line ({len(MAINTAINED_INDICES)} indices)...", flush=True)
    idx_dfs, _ = thread_fetch(stock_kline_wrapper, MAINTAINED_INDICES, buf_start, args.end_date, 'index', 2)
    if idx_dfs:
        all_idx = pd.concat([d.pipe(process_index_kline) if not d.empty else d for d in idx_dfs], ignore_index=True)
        write_gz_csv(all_idx, os.path.join(args.out_dir, "kline_indices.csv.gz"))
        print(f"[2/4] total index rows: {len(all_idx)}", flush=True)
    else:
        print("[2/4] no index data", flush=True)

    # 3) Factors
    print(f"\n[3/4] Fetching adjustment factors (threaded x{args.threads}, {len(codes)} codes)...", flush=True)
    factor_dfs, _ = thread_fetch(factor_wrapper, codes, buf_start, args.end_date, 'factor', args.threads)
    if factor_dfs:
        all_factors = pd.concat(factor_dfs, ignore_index=True)
        write_gz_csv(all_factors, os.path.join(args.out_dir, "factors.csv.gz"))
        print(f"[3/4] total factor rows: {len(all_factors)}", flush=True)
    else:
        print("[3/4] no factor data", flush=True)

    # 4) Securities
    if not args.skip_securities:
        print(f"\n[4/4] Fetching securities list...", flush=True)
        df = fetch_stock_basic()
        if df is None or df.empty:
            print("  [4/4] empty/error", flush=True)
        else:
            df['ipoDate'] = df['ipoDate'].replace('', '1990-12-19')
            df['outDate'] = df['outDate'].replace('', '2999-12-31')
            df['type'] = pd.to_numeric(df['type'], errors='coerce').fillna(0).astype(int)
            df = df[df['code'] != '']
            write_gz_csv(df, os.path.join(args.out_dir, "securities_basic.csv.gz"))
            print(f"[4/4] total securities: {len(df)}", flush=True)
    else:
        print("\n[4/4] (skipped)", flush=True)

    try:
        bs.logout()
    except Exception:
        pass
    print("\n=== DONE ===", flush=True)
    print(f"Output: {args.out_dir}", flush=True)
    for f in sorted(os.listdir(args.out_dir)):
        sz = os.path.getsize(os.path.join(args.out_dir, f))
        print(f"  {f}  {sz/1024:.1f}KB", flush=True)

if __name__ == '__main__':
    main()
