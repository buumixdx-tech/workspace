
import pandas as pd
import baostock as bs
import sys
import os
sys.path.append(os.getcwd())
try:
    from src.storage.data_loader import get_price
except ImportError:
    # If running from src
    sys.path.append(os.path.join(os.getcwd(), 'src'))
    from src.storage.data_loader import get_price

def verify_stock(code, start='2025-01-01', end='2025-06-30'):
    print(f"Verifying {code} ({start} ~ {end})...")
    
    # 1. Fetch from New Loader (CK)
    df_ck = get_price(code, start, end, adjust='qfq')
    if df_ck.empty:
        print("CK returned empty!")
        return False
        
    df_ck['date'] = df_ck['date'].astype(str)
    
    # 2. Fetch from Baostock Online (Truth)
    bs.login()
    fields = "date,open,high,low,close,volume,amount"
    rs = bs.query_history_k_data_plus(code, fields, start_date=start, end_date=end, frequency="d", adjustflag="2") # 2=qfq
    data_list = []
    while rs.next():
        data_list.append(rs.get_row_data())
    bs.logout()
    
    if not data_list:
        print("Baostock Online returned empty!")
        return False
        
    df_bs = pd.DataFrame(data_list, columns=fields.split(','))
    for c in ['open','high','low','close','volume','amount']:
        df_bs[c] = pd.to_numeric(df_bs[c])
        
    # 3. Compare
    # Merge on date
    df_compare = pd.merge(df_ck, df_bs, on='date', suffixes=('_ck', '_bs'))
    
    # Check Close Price diff
    df_compare['diff_close'] = abs(df_compare['close_ck'] - df_compare['close_bs'])
    df_compare['diff_ratio'] = df_compare['diff_close'] / df_compare['close_bs']
    
    max_diff = df_compare['diff_ratio'].max()
    print(f"Max Diff Ratio (Close): {max_diff:.6f}")
    
    if max_diff > 0.01: # 1% tolerance (Baostock factor precision sometimes varies slightly)
        print("FAIL: Difference too large.")
        print(df_compare[['date', 'close_ck', 'close_bs', 'diff_ratio']].sort_values('diff_ratio', ascending=False).head())
        return False
    else:
        print("PASS: Data matches within tolerance.")
        return True

if __name__ == "__main__":
    # Test a few cases
    # 1. Old stock
    verify_stock("sh.600000", "2025-01-01", "2025-06-01")
    # 2. New stock (IPO after 2021)
    verify_stock("sz.301333", "2025-01-01", "2025-06-01")
    # 3. Suspended stock? (Need to find one)
