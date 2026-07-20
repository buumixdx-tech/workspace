"""
remote_fetch_incremental.py
============================

Runs on jcloud (111.228.51.56) where baostock is NOT IP-blocked.
Fetches incremental data (K-line, factors) from baostock and dumps to
gzip-compressed CSV files for buumiPC to download via scp.

This script is a *pure fetcher* - it does NOT touch ClickHouse.
It re-uses the same fetching logic and limit-calc as the local pipeline
to keep the data format 100% compatible with what stock_kline_day /
index_kline_day / adjust_factor tables expect.

Usage:
    python remote_fetch_incremental.py \
        --start-date 2026-06-13 \
        --end-date 2026-06-17 \
        --out-dir /tmp/baostock_pull/20260617_130000
"""

import argparse
import datetime
import os
import sys
import time
import random
import traceback
import gzip
import multiprocessing
import concurrent.futures
from io import StringIO

import pandas as pd
import baostock as bs

# ============================================================
# Constants - same as the local pipeline
# ============================================================

# Maintained indices (from local config.toml)
MAINTAINED_INDICES = [
    "sh.000001",  # 上证指数
    "sh.000016",  # 上证50
    "sh.000300",  # 沪深300
    "sh.000905",  # 中证500
    "sh.000852",  # 中证1000
    "sz.000510",  # 中证A500
    "sz.399006",  # 创业板指
    "sz.000688",  # 科创50
    "sz.399001",  # 深证成指
]

KLINE_FIELDS = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST"
FACTOR_FIELDS = "code,dividOperateDate,foreAdjustFactor,backAdjustFactor"

MAX_WORKERS = 16

# ============================================================
# Limit calculation (copy of etl/limit_calc.py logic for stocks)
# ============================================================

def _round_to_cent(x):
    return round(float(x) + 1e-9, 2)

def _calc_prev_close(grp):
    return grp['close'].shift(1)

def calculate_limits(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['preclose_calc'] = df.groupby('code', group_keys=False).apply(_calc_prev_close)
    df['preclose_calc'] = df['preclose_calc'].fillna(df['close'])
    is_st = df['isST'].fillna(0).astype(int) == 1
    rate = pd.Series(0.10, index=df.index)
    rate[is_st] = 0.05
    df['limit_up_price'] = (df['preclose_calc'] * (1 + rate)).apply(_round_to_cent)
    df['limit_down_price'] = (df['preclose_calc'] * (1 - rate)).apply(_round_to_cent)
    df = df.drop(columns=['preclose_calc'])
    return df

# ============================================================
# Baostock session (process-local)
# ============================================================

_IS_LOGGED_IN = False

def force_relogin(retries=3):
    global _IS_LOGGED_IN
    try:
        bs.logout()
    except Exception:
        pass
    for i in range(retries):
        try:
            time.sleep(random.uniform(0.1, 0.5) * (i + 1))
            lg = bs.login()
            if lg.error_code == '0':
                _IS_LOGGED_IN = True
                return True
        except Exception:
            pass
    _IS_LOGGED_IN = False
    return False

def ensure_login():
    if not _IS_LOGGED_IN:
        return force_relogin()
    return True

def fetch_kline(code, start_date, end_date):
    if not ensure_login():
        return None, "LOGIN_FAILED"
    for attempt in range(3):
        try:
            rs = bs.query_history_k_data_plus(
                code, KLINE_FIELDS,
                start_date=start_date, end_date=end_date,
                frequency="d", adjustflag="3"
            )
            if rs.error_code == '10001001':
                global _IS_LOGGED_IN
                _IS_LOGGED_IN = False
                if not ensure_login():
                    continue
                continue
            if rs.error_code != '0':
                return None, f"API_ERROR_{rs.error_code}: {rs.error_msg}"
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            if not data_list:
                return pd.DataFrame(), None
            df = pd.DataFrame(data_list, columns=KLINE_FIELDS.split(','))
            return df, None
        except Exception as e:
            return None, f"EXC: {e}"
    return None, "MAX_RETRIES"

def fetch_factors(code, start_date, end_date):
    if not ensure_login():
        return None, "LOGIN_FAILED"
    for attempt in range(3):
        try:
            rs = bs.query_adjust_factor(code, start_date=start_date, end_date=end_date)
            if rs.error_code == '10001001':
                global _IS_LOGGED_IN
                _IS_LOGGED_IN = False
                if not ensure_login():
                    continue
                continue
            if rs.error_code != '0':
                return None, f"API_ERROR_{rs.error_code}: {rs.error_msg}"
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            if not data_list:
                return pd.DataFrame(), None
            df = pd.DataFrame(data_list, columns=FACTOR_FIELDS.split(','))
            return df, None
        except Exception as e:
            return None, f"EXC: {e}"
    return None, "MAX_RETRIES"

# ============================================================
# Worker tasks (run in subprocess - has its own baostock session)
# ============================================================

def stock_kline_worker(args):
    code, start_date, end_date = args
    df, err = fetch_kline(code, start_date, end_date)
    if err or df is None or df.empty:
        return ('stock', code, None, err)
    # process
    numeric_cols = ['open','high','low','close','preclose','volume','amount','turn','pctChg']
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    df['tradestatus'] = pd.to_numeric(df['tradestatus'], errors='coerce').fillna(1).astype(int)
    df['isST'] = pd.to_numeric(df['isST'], errors='coerce').fillna(0).astype(int)
    df['adjustflag'] = 3
    df = calculate_limits(df)
    def _status(row):
        c = row['close']; h = row['high']
        up = row['limit_up_price']; down = row['limit_down_price']
        if c >= up: return 1
        if c <= down: return 2
        if h >= up and c < up: return 3
        return 0
    df['limit_status'] = df.apply(_status, axis=1)
    return ('stock', code, df, None)

def index_kline_worker(args):
    code, start_date, end_date = args
    df, err = fetch_kline(code, start_date, end_date)
    if err or df is None or df.empty:
        return ('index', code, None, err)
    numeric_cols = ['open','high','low','close','preclose','volume','amount','pctChg']
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    return ('index', code, df, None)

def factor_worker(args):
    code, start_date, end_date = args
    df, err = fetch_factors(code, start_date, end_date)
    if err or df is None or df.empty:
        return ('factor', code, None, err)
    df['foreAdjustFactor'] = pd.to_numeric(df['foreAdjustFactor'], errors='coerce')
    df['backAdjustFactor'] = pd.to_numeric(df['backAdjustFactor'], errors='coerce')
    return ('factor', code, df, None)

# ============================================================
# Stock list fetching
# ============================================================

def fetch_stock_basic():
    if not ensure_login():
        return None, "LOGIN_FAILED"
    rs = bs.query_stock_basic()
    if rs.error_code != '0':
        return None, f"API_ERROR_{rs.error_code}: {rs.error_msg}"
    data_list = []
    while rs.error_code == '0' and rs.next():
        data_list.append(rs.get_row_data())
    if not data_list:
        return pd.DataFrame(), None
    df = pd.DataFrame(data_list, columns=rs.fields)
    return df, None

def get_all_stock_codes():
    if not ensure_login():
        return []
    today = datetime.date.today().strftime("%Y-%m-%d")
    rs = bs.query_all_stock(day=today)
    if rs.error_code != '0':
        return []
    codes = []
    while rs.error_code == '0' and rs.next():
        code = rs.get_row_data()[0]
        if code.startswith(('sh.', 'sz.')):
            codes.append(code)
    return codes

# ============================================================
# Dump helpers
# ============================================================

def write_gz_csv(df, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    buf = StringIO()
    df.to_csv(buf, index=False)
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        f.write(buf.getvalue())
    sz = os.path.getsize(path)
    print(f"  wrote {path}  rows={len(df)}  size={sz/1024:.1f}KB")

def parallel_fetch(worker_fn, codes, start_date, end_date, label, max_workers=MAX_WORKERS):
    """Run worker_fn in a ProcessPool and collect results."""
    tasks = [(c, start_date, end_date) for c in codes]
    results = []
    err_count = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(worker_fn, t): t[0] for t in tasks}
        done = 0
        total = len(tasks)
        for fut in concurrent.futures.as_completed(future_map):
            done += 1
            try:
                kind, code, df, err = fut.result()
                if err:
                    err_count += 1
                    if err_count <= 5:
                        print(f"  [{label}][{code}] err: {err}")
                else:
                    results.append(df)
            except Exception as e:
                err_count += 1
                if err_count <= 5:
                    print(f"  [{label}] exc: {e}")
            if done % 200 == 0:
                print(f"  ... {done}/{total} done (err={err_count})")
    print(f"  [{label}] total: {done} ok={done-err_count} err={err_count}")
    return results, err_count

# ============================================================
# Main
# ============================================================

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--start-date', required=True)
    p.add_argument('--end-date', default=datetime.date.today().strftime("%Y-%m-%d"))
    p.add_argument('--out-dir', required=True)
    p.add_argument('--buffer-days', type=int, default=3)
    p.add_argument('--skip-securities', action='store_true')
    p.add_argument('--max-workers', type=int, default=MAX_WORKERS)
    args = p.parse_args()

    start = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()
    buf_start = start - datetime.timedelta(days=args.buffer_days)
    buf_start_str = buf_start.strftime("%Y-%m-%d")

    os.makedirs(args.out_dir, exist_ok=True)

    print("=" * 60)
    print(f"Remote baostock fetch (parallel)")
    print(f"  start_date:  {args.start_date}  (buffered: {buf_start})")
    print(f"  end_date:    {args.end_date}")
    print(f"  out_dir:     {args.out_dir}")
    print(f"  workers:     {args.max_workers}")
    print("=" * 60)

    if not force_relogin():
        print("FATAL: baostock login failed")
        sys.exit(1)
    print("[login] OK")

    # Get all A-share codes (single-threaded; very fast)
    print("\n[0/4] Discovering A-share codes...")
    codes = get_all_stock_codes()
    print(f"  got {len(codes)} active A-share codes")

    # 1) Stock K-line
    print("\n[1/4] Fetching stock K-line data (parallel)...")
    t0 = time.time()
    stock_dfs, _ = parallel_fetch(stock_kline_worker, codes, buf_start_str, args.end_date, 'stock', args.max_workers)
    if stock_dfs:
        all_stocks = pd.concat(stock_dfs, ignore_index=True)
        write_gz_csv(all_stocks, os.path.join(args.out_dir, "kline_stocks.csv.gz"))
        print(f"[1/4] total stock rows: {len(all_stocks)}  elapsed: {time.time()-t0:.1f}s")
    else:
        print("[1/4] no stock data")

    # 2) Index K-line
    print("\n[2/4] Fetching index K-line data...")
    t0 = time.time()
    idx_dfs, _ = parallel_fetch(index_kline_worker, MAINTAINED_INDICES, buf_start_str, args.end_date, 'index', max(4, args.max_workers//4))
    if idx_dfs:
        all_idx = pd.concat(idx_dfs, ignore_index=True)
        write_gz_csv(all_idx, os.path.join(args.out_dir, "kline_indices.csv.gz"))
        print(f"[2/4] total index rows: {len(all_idx)}  elapsed: {time.time()-t0:.1f}s")
    else:
        print("[2/4] no index data")

    # 3) Adjustment factors
    print("\n[3/4] Fetching adjustment factors (parallel)...")
    t0 = time.time()
    factor_dfs, _ = parallel_fetch(factor_worker, codes, buf_start_str, args.end_date, 'factor', args.max_workers)
    if factor_dfs:
        all_factors = pd.concat(factor_dfs, ignore_index=True)
        write_gz_csv(all_factors, os.path.join(args.out_dir, "factors.csv.gz"))
        print(f"[3/4] total factor rows: {len(all_factors)}  elapsed: {time.time()-t0:.1f}s")
    else:
        print("[3/4] no factor data")

    # 4) Securities list
    if not args.skip_securities:
        print("\n[4/4] Fetching securities list...")
        df, err = fetch_stock_basic()
        if err:
            print(f"  [4/4] err: {err}")
        elif df is None or df.empty:
            print("  [4/4] empty")
        else:
            df['ipoDate'] = df['ipoDate'].replace('', '1990-12-19')
            df['outDate'] = df['outDate'].replace('', '2999-12-31')
            df['type'] = pd.to_numeric(df['type'], errors='coerce').fillna(0).astype(int)
            df = df[df['code'] != '']
            write_gz_csv(df, os.path.join(args.out_dir, "securities_basic.csv.gz"))
            print(f"[4/4] total securities: {len(df)}")
    else:
        print("\n[4/4] (skipped)")

    try:
        bs.logout()
    except Exception:
        pass

    print("\n=== DONE ===")
    print(f"Output: {args.out_dir}")
    for f in sorted(os.listdir(args.out_dir)):
        sz = os.path.getsize(os.path.join(args.out_dir, f))
        print(f"  {f}  {sz/1024:.1f}KB")

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
