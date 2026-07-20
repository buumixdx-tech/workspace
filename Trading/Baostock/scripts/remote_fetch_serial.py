"""
remote_fetch_serial.py - single-process baostock fetcher (no parallel).
Slower but baostock's SDK is single-session, so parallelism breaks the
connection. We trade speed for stability.
"""

import argparse
import datetime
import os
import sys
import time
import gzip
from io import StringIO

import pandas as pd
import baostock as bs

# Same constants as remote_fetch_incremental.py
MAINTAINED_INDICES = [
    "sh.000001", "sh.000016", "sh.000300", "sh.000905", "sh.000852",
    "sz.000510", "sz.399006", "sz.000688", "sz.399001",
]
KLINE_FIELDS = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST"
FACTOR_FIELDS = "code,dividOperateDate,foreAdjustFactor,backAdjustFactor"

def _round_to_cent(x):
    return round(float(x) + 1e-9, 2)

def calculate_limits(df):
    df = df.copy()
    df['preclose_calc'] = df.groupby('code', group_keys=False)['close'].apply(lambda s: s.shift(1))
    df['preclose_calc'] = df['preclose_calc'].fillna(df['close'])
    is_st = df['isST'].fillna(0).astype(int) == 1
    rate = pd.Series(0.10, index=df.index)
    rate[is_st] = 0.05
    df['limit_up_price'] = (df['preclose_calc'] * (1 + rate)).apply(_round_to_cent)
    df['limit_down_price'] = (df['preclose_calc'] * (1 - rate)).apply(_round_to_cent)
    df = df.drop(columns=['preclose_calc'])
    return df

def ensure_login():
    for attempt in range(5):
        try:
            bs.logout()
        except Exception:
            pass
        # wait longer to dodge baostock rate-limit / IP throttling
        if attempt > 0:
            wait = 30 * attempt
            print(f"[login] backoff {wait}s before retry...", flush=True)
            time.sleep(wait)
        try:
            lg = bs.login()
            if lg.error_code == '0':
                print(f"[login] OK (attempt {attempt+1})", flush=True)
                return True
            else:
                print(f"[login] attempt {attempt+1} failed: {lg.error_code} {lg.error_msg}", flush=True)
        except Exception as e:
            print(f"[login] attempt {attempt+1} exception: {e}", flush=True)
    return False

def fetch_kline(code, start_date, end_date):
    for attempt in range(3):
        try:
            rs = bs.query_history_k_data_plus(
                code, KLINE_FIELDS,
                start_date=start_date, end_date=end_date,
                frequency="d", adjustflag="3"
            )
            if rs.error_code == '10001001':  # not logged in
                if not ensure_login():
                    return None, "LOGIN_RETRY_FAILED"
                continue
            if rs.error_code != '0':
                return None, f"API_{rs.error_code}"
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            if not data_list:
                return pd.DataFrame(), None
            return pd.DataFrame(data_list, columns=KLINE_FIELDS.split(',')), None
        except Exception as e:
            return None, f"EXC: {e}"
        time.sleep(0.05)
    return None, "MAX_RETRIES"

def fetch_factors(code, start_date, end_date):
    for attempt in range(3):
        try:
            rs = bs.query_adjust_factor(code, start_date=start_date, end_date=end_date)
            if rs.error_code == '10001001':
                if not ensure_login():
                    return None, "LOGIN_RETRY_FAILED"
                continue
            if rs.error_code != '0':
                return None, f"API_{rs.error_code}"
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            if not data_list:
                return pd.DataFrame(), None
            return pd.DataFrame(data_list, columns=FACTOR_FIELDS.split(',')), None
        except Exception as e:
            return None, f"EXC: {e}"
        time.sleep(0.05)
    return None, "MAX_RETRIES"

def process_stock_kline(df):
    if df.empty:
        return df
    for c in ['open','high','low','close','preclose','volume','amount','turn','pctChg']:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    df['tradestatus'] = pd.to_numeric(df['tradestatus'], errors='coerce').fillna(1).astype(int)
    df['isST'] = pd.to_numeric(df['isST'], errors='coerce').fillna(0).astype(int)
    df['adjustflag'] = 3
    df = calculate_limits(df)
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
    print(f"  wrote {path}  rows={len(df)}  size={os.path.getsize(path)/1024:.1f}KB", flush=True)

def get_all_stock_codes():
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
    rs = bs.query_stock_basic()
    if rs.error_code != '0':
        return None
    data = []
    while rs.error_code == '0' and rs.next():
        data.append(rs.get_row_data())
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data, columns=rs.fields)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--start-date', required=True)
    p.add_argument('--end-date', default=datetime.date.today().strftime("%Y-%m-%d"))
    p.add_argument('--out-dir', required=True)
    p.add_argument('--buffer-days', type=int, default=3)
    p.add_argument('--skip-securities', action='store_true')
    args = p.parse_args()

    start = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()
    buf_start = (start - datetime.timedelta(days=args.buffer_days)).strftime("%Y-%m-%d")
    os.makedirs(args.out_dir, exist_ok=True)

    print("=" * 60, flush=True)
    print(f"Remote baostock fetch (SERIAL, stable)", flush=True)
    print(f"  start_date:  {args.start_date}  (buffered: {buf_start})", flush=True)
    print(f"  end_date:    {args.end_date}", flush=True)
    print(f"  out_dir:     {args.out_dir}", flush=True)
    print("=" * 60, flush=True)

    if not ensure_login():
        print("FATAL: baostock login failed", flush=True)
        sys.exit(1)

    print("\n[0/4] Discovering A-share codes...", flush=True)
    codes = get_all_stock_codes()
    print(f"  got {len(codes)} active A-share codes", flush=True)

    # 1) Stock K-line
    print(f"\n[1/4] Fetching stock K-line (serial, {len(codes)} codes)...", flush=True)
    t0 = time.time()
    stock_rows = []
    err = 0
    for i, code in enumerate(codes):
        df, e = fetch_kline(code, buf_start, args.end_date)
        if e:
            err += 1
            if err <= 3:
                print(f"  [{code}] err: {e}", flush=True)
            continue
        if not df.empty:
            stock_rows.append(process_stock_kline(df))
        if (i + 1) % 500 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(codes) - i - 1) / rate
            print(f"  ... {i+1}/{len(codes)} done (err={err}) {rate:.1f} req/s, ETA {eta:.0f}s", flush=True)
    if stock_rows:
        all_stocks = pd.concat(stock_rows, ignore_index=True)
        write_gz_csv(all_stocks, os.path.join(args.out_dir, "kline_stocks.csv.gz"))
        print(f"[1/4] total stock rows: {len(all_stocks)} err={err} elapsed={time.time()-t0:.1f}s", flush=True)
    else:
        print("[1/4] no stock data", flush=True)

    # 2) Index K-line
    print(f"\n[2/4] Fetching index K-line ({len(MAINTAINED_INDICES)} indices)...", flush=True)
    t0 = time.time()
    idx_rows = []
    for code in MAINTAINED_INDICES:
        df, e = fetch_kline(code, buf_start, args.end_date)
        if e or df.empty:
            continue
        idx_rows.append(process_index_kline(df))
    if idx_rows:
        all_idx = pd.concat(idx_rows, ignore_index=True)
        write_gz_csv(all_idx, os.path.join(args.out_dir, "kline_indices.csv.gz"))
        print(f"[2/4] total index rows: {len(all_idx)} elapsed={time.time()-t0:.1f}s", flush=True)
    else:
        print("[2/4] no index data", flush=True)

    # 3) Factors
    print(f"\n[3/4] Fetching adjustment factors (serial, {len(codes)} codes)...", flush=True)
    t0 = time.time()
    factor_rows = []
    ferr = 0
    for i, code in enumerate(codes):
        df, e = fetch_factors(code, buf_start, args.end_date)
        if e:
            ferr += 1
            continue
        if not df.empty:
            factor_rows.append(process_factor(df))
        if (i + 1) % 500 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(codes) - i - 1) / rate
            print(f"  ... {i+1}/{len(codes)} done (err={ferr}) {rate:.1f} req/s, ETA {eta:.0f}s", flush=True)
    if factor_rows:
        all_factors = pd.concat(factor_rows, ignore_index=True)
        write_gz_csv(all_factors, os.path.join(args.out_dir, "factors.csv.gz"))
        print(f"[3/4] total factor rows: {len(all_factors)} err={ferr} elapsed={time.time()-t0:.1f}s", flush=True)
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
