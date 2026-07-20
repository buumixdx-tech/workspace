"""
remote_fetch_factors_only.py - baostock factor fetcher (incremental, single-process).

Uses a single baostock socket (serial). Optimized for slow connections.
Outputs:
  - factors.csv.gz  (gzip-compressed CSV with: code,dividOperateDate,foreAdjustFactor,backAdjustFactor)

The jcloud server's IP isn't baostock-banned, but multi-process breaks the
single-socket design. Single-process serial is the only stable path.
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

FACTOR_FIELDS = "code,dividOperateDate,foreAdjustFactor,backAdjustFactor"

def ensure_login():
    for attempt in range(5):
        try:
            bs.logout()
        except Exception:
            pass
        if attempt > 0:
            wait = 20 * attempt
            print(f"[login] backoff {wait}s before retry {attempt+1}...", flush=True)
            time.sleep(wait)
        try:
            lg = bs.login()
            if lg.error_code == '0':
                print(f"[login] OK (attempt {attempt+1})", flush=True)
                return True
            print(f"[login] attempt {attempt+1} failed: {lg.error_code} {lg.error_msg}", flush=True)
        except Exception as e:
            print(f"[login] attempt {attempt+1} exc: {e}", flush=True)
    return False

def fetch_factors(code, start_date, end_date):
    for attempt in range(3):
        try:
            rs = bs.query_adjust_factor(code, start_date=start_date, end_date=end_date)
            if rs.error_code == '10001001':
                return None, "RELOGIN"
            if rs.error_code != '0':
                return None, f"API_{rs.error_code}: {rs.error_msg}"
            data = []
            while rs.next():
                data.append(rs.get_row_data())
            if not data:
                return pd.DataFrame(), None
            return pd.DataFrame(data, columns=FACTOR_FIELDS.split(',')), None
        except Exception as e:
            return None, f"EXC: {e}"
    return None, "MAX_RETRIES"

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

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--start-date', required=True, help='fetch factors from this date')
    p.add_argument('--end-date', default=datetime.date.today().strftime("%Y-%m-%d"))
    p.add_argument('--out-dir', required=True)
    p.add_argument('--out-name', default='factors.csv.gz')
    args = p.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print("=" * 60, flush=True)
    print(f"Remote baostock factor fetch (SERIAL)", flush=True)
    print(f"  start_date:  {args.start_date}", flush=True)
    print(f"  end_date:    {args.end_date}", flush=True)
    print(f"  out_dir:     {args.out_dir}", flush=True)
    print("=" * 60, flush=True)

    if not ensure_login():
        print("FATAL: baostock login failed", flush=True)
        sys.exit(1)

    print("\n[0/2] Discovering A-share codes...", flush=True)
    codes = get_all_stock_codes()
    print(f"  got {len(codes)} active A-share codes", flush=True)

    print(f"\n[1/2] Fetching adjustment factors (serial, {len(codes)} codes)...", flush=True)
    t0 = time.time()
    rows = []
    err = 0
    relogin_count = 0
    for i, code in enumerate(codes):
        df, e = fetch_factors(code, args.start_date, args.end_date)
        if e == "RELOGIN":
            if relogin_count < 3 and ensure_login():
                relogin_count += 1
                # retry once
                df, e = fetch_factors(code, args.start_date, args.end_date)
            else:
                e = "RELOGIN_EXHAUSTED"
        if e:
            err += 1
            if err <= 3:
                print(f"  [{code}] err: {e}", flush=True)
            continue
        if not df.empty:
            rows.append(process_factor(df))
        if (i + 1) % 100 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(codes) - i - 1) / rate
            print(f"  ... {i+1}/{len(codes)} err={err} {rate:.1f} req/s ETA {eta:.0f}s", flush=True)

    if rows:
        all_factors = pd.concat(rows, ignore_index=True)
        write_gz_csv(all_factors, os.path.join(args.out_dir, args.out_name))
        print(f"[1/2] total factor rows: {len(all_factors)} err={err} elapsed={time.time()-t0:.1f}s", flush=True)
    else:
        print("[1/2] no factor data", flush=True)

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
