
import baostock as bs
import pandas as pd
import requests
import datetime
import os
import sys

# 使用统一配置加载器
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from config_loader import CK_HOST, CK_AUTH


def get_all_stocks():
    print("Fetching all stock codes (including delisted)...")
    lg = bs.login()
    if lg.error_code != '0':
        print(f"Login failed: {lg.error_msg}")
        return None

    # query_all_stock only returns *currently listed* stocks for the specific date.
    # To find delisted stocks or new stocks, we need to query a recent date?
    # Actually baostock `query_stock_basic` usually gives basic info including IPO.
    # Let's verify `query_stock_basic`.
    
    rs = bs.query_stock_basic()
    
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    
    bs.logout()
    
    if not data_list:
        print("No stock basic info found.")
        return None
        
    # Columns usually: code, code_name, ipoDate, outDate, type, status
    df = pd.DataFrame(data_list, columns=rs.fields)
    return df


def get_existing_codes():
    try:
        r = requests.post(CK_HOST, params={'query': "SELECT code FROM stock_data.securities_info"}, auth=CK_AUTH)
        if r.status_code == 200:
            return set(r.text.strip().split('\n'))
    except:
        pass
    return set()

def process_and_insert(df):
    # Schema: code, symbol, ipo_date, out_date, type
    
    # Cleaning
    df['ipoDate'] = df['ipoDate'].replace('', '1990-12-19')
    df['outDate'] = df['outDate'].replace('', '2999-12-31')
    df['type'] = pd.to_numeric(df['type'], errors='coerce').fillna(0).astype(int)
    
    # We only care about stocks that have at least a code and type
    df = df[df['code'] != '']
    
    print(f"Preparing {len(df)} records for ClickHouse...")
    
    # Use CSV for robustness
    from io import StringIO
    csv_buffer = StringIO()
    
    # We need to match the columns in the table: code, symbol, ipo_date, out_date, type
    export_df = df[['code', 'code_name', 'ipoDate', 'outDate', 'type']]
    export_df.to_csv(csv_buffer, index=False, header=False)
    
    csv_data = csv_buffer.getvalue()
    
    # 1. Truncate
    try:
        requests.post(CK_HOST, data="TRUNCATE TABLE stock_data.securities_info", auth=CK_AUTH)
        print("Table truncated.")
    except:
        pass
        
    # 2. Insert via CSV
    url = f"{CK_HOST}/?query=INSERT+INTO+stock_data.securities_info+(code,symbol,ipo_date,out_date,type)+FORMAT+CSV"
    try:
        r = requests.post(url, data=csv_data.encode('utf-8'), auth=CK_AUTH)
        if r.status_code == 200:
            print(f"Successfully loaded {len(df)} records into securities_info.")
            return True
        else:
            print(f"Insert failed: {r.text}")
            return False
    except Exception as e:
        print(f"Exception during insert: {e}")
        return False

def main():
    df = get_all_stocks()
    if df is not None:
        process_and_insert(df)

def run_etl():
    """External entry point for UI."""
    try:
        # 1. Get Old
        old_codes = get_existing_codes()
        
        # 2. Get New (Baostock)
        df = get_all_stocks()
        if df is None:
            return False, "Failed to fetch stock list from Baostock."
            
        new_codes = set(df['code'].tolist())
        
        # 3. Diff
        added = new_codes - old_codes
        removed = old_codes - new_codes
        
        # 4. Update DB
        success = process_and_insert(df)
        
        if success:
            msg = f"证券列表刷新完毕。当前总数: {len(new_codes)}。"
            if added:
                msg += f" 🔥 新增 {len(added)} 只标的 (如 {list(added)[:3]}...)"
            if removed:
                msg += f" 🗑️ 移除 {len(removed)} 只旧标的"
            if not added and not removed:
                msg += " (无变动)"
                
            return True, msg
        else:
            return False, "DB Insert Failed"
            
    except Exception as e:
        return False, f"Securities ETL Error: {e}"

if __name__ == "__main__":
    main()



