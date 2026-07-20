
import pandas as pd
import os
from market.ck_client import ClickHouseClient

def fill_data():
    ck = ClickHouseClient()
    target_date = '2026-01-29'
    
    p1_file = 'data/stock_analysis/result_p1_20260130101152.xlsx'
    pool_file = 'data/stock_analysis/stockpool.xlsx'
    
    all_codes = set()
    
    # 1. Read files and collect codes
    df_p1 = None
    if os.path.exists(p1_file):
        df_p1 = pd.read_excel(p1_file)
        # Use ffilled codes for matching
        filled_codes = df_p1['股票代码'].ffill()
        all_codes.update([str(c).lower() for c in filled_codes.unique() if pd.notna(c)])
        
    df_pool_raw = None
    if os.path.exists(pool_file):
        df_pool_raw = pd.read_excel(pool_file)
        code_col = 'code' if 'code' in df_pool_raw.columns else '股票代码'
        all_codes.update([str(c).lower() for c in df_pool_raw[code_col].unique() if pd.notna(c)])
        
    if not all_codes:
        print("No codes found.")
        ck.close()
        return

    codes_str = "'" + "','".join(all_codes) + "'"
    
    # 2. Derive shares from latest snapshots
    snapshot_sql = f"""
    SELECT 
        code, 
        argMax(total_market_cap / price, snapshot_time) as total_shares,
        argMax(float_market_cap / price, snapshot_time) as float_shares
    FROM stock_snapshot_intraday
    WHERE code IN ({codes_str})
      AND price > 0
    GROUP BY code
    """
    shares_data = ck.query_df(snapshot_sql)
    shares_map = shares_data.set_index('code')
    print(f"Derived shares for {len(shares_map)} stocks from snapshots.")

    # 3. Fetch K-line data for target date
    kline_sql = f"""
    SELECT 
        k.code, 
        k.close, 
        k.preclose,
        k.volume, 
        k.turn,
        k.tradestatus,
        k.isST,
        i.symbol
    FROM stock_kline_day k
    LEFT JOIN securities_info i ON k.code = i.code
    WHERE k.date = '{target_date}'
      AND k.code IN ({codes_str})
    """
    kline_data = ck.query_df(kline_sql)
    kline_map = kline_data.set_index('code')
    print(f"Fetched K-line data for {len(kline_map)} stocks on {target_date}.")

    # 4. Update P1 file
    if df_p1 is not None:
        # Use ffilled codes for lookup but apply values to every row if needed
        # Actually, for P1, we want every row (including those that were NaN) to have the value
        # if they belong to the same stock.
        filled_codes = df_p1['股票代码'].ffill()
        for idx, row in df_p1.iterrows():
            code = str(filled_codes.iloc[idx]).lower()
            if code in kline_map.index:
                k = kline_map.loc[code]
                close = k['close']
                total_shares = shares_map.loc[code, 'total_shares'] if code in shares_map.index else 0
                total_mcap = close * total_shares
                
                float_mcap = 0
                if k['turn'] > 0:
                    float_mcap = close * (k['volume'] / (k['turn'] / 100))
                elif code in shares_map.index:
                    float_mcap = close * shares_map.loc[code, 'float_shares']
                
                df_p1.at[idx, '总市值'] = int(total_mcap)
                df_p1.at[idx, '流通市值'] = int(float_mcap)
        
        df_p1.to_excel(p1_file, index=False)
        print(f"Successfully updated {p1_file}")

    # 5. Update stockpool.xlsx
    if df_pool_raw is not None:
        code_col = 'code' if 'code' in df_pool_raw.columns else '股票代码'
        rows = []
        for _, pool_row in df_pool_raw.iterrows():
            code = str(pool_row[code_col]).lower()
            if code in kline_map.index:
                k = kline_map.loc[code]
                # Round prices to 2 decimal places
                close = round(float(k['close']), 2)
                preclose = round(float(k['preclose']), 2)
                
                total_shares = shares_map.loc[code, 'total_shares'] if code in shares_map.index else 0
                total_mcap = close * total_shares
                
                float_mcap = 0
                if k['turn'] > 0:
                    float_mcap = close * (k['volume'] / (k['turn'] / 100))
                elif code in shares_map.index:
                    float_mcap = close * shares_map.loc[code, 'float_shares']
                
                rows.append({
                    '股票代码': code.upper(),
                    '股票简称': k['symbol'],
                    '今天收盘价': close,
                    '前一交易日收盘价': preclose,
                    '总市值': int(total_mcap),
                    '流通市值': int(float_mcap),
                    '交易状态': '正常' if k['tradestatus'] == 1 else '停牌',
                    '停牌日期': '',
                    '是否st': '是' if k['isST'] == 1 else '否'
                })
        
        df_pool_final = pd.DataFrame(rows)
        if not df_pool_final.empty:
            df_pool_final = df_pool_final[['股票代码', '股票简称', '今天收盘价', '前一交易日收盘价', '总市值', '流通市值', '交易状态', '停牌日期', '是否st']]
            df_pool_final.to_excel(pool_file, index=False)
            print(f"Successfully updated {pool_file}")
            
    ck.close()

if __name__ == "__main__":
    fill_data()
