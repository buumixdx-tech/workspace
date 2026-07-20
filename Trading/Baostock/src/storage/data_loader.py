import pandas as pd
import os
import toml
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config():
    # Helper to load config from anywhere in src
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_path = os.path.join(base_dir, 'config.toml')
    return toml.load(config_path)

CONFIG = load_config()

from datetime import datetime
from src.storage.ck_client import ck_client

def get_price(code, start_date=None, end_date=None, adjust='hfq'):
    """
    Universal Data Loader (ClickHouse Version).
    
    Args:
        code (str): Stock code, e.g., 'sh.600000'
        start_date (str): 'YYYY-MM-DD'
        end_date (str): 'YYYY-MM-DD'
        adjust (str): 'none', 'qfq' (Pre-Adjust), 'hfq' (Post-Adjust)
        
    Returns:
        pd.DataFrame: OHLCV data from ClickHouse.
    """
    return get_price_from_ck(code, start_date, end_date, adjust)

def get_price_from_ck(code, start_date=None, end_date=None, adjust='hfq'):
    """
    Fetch price data from ClickHouse.
    Handles 'limit_up/down' and 'limit_status' automatically.
    """
    # 1. Determine table (Index or Stock)
    is_index = code.startswith('sh.000') or code.startswith('sz.399')
    table = "stock_data.index_kline_day" if is_index else "stock_data.stock_kline_day"
    
    # 2. Build SQL
    # Get columns explicitly to avoid type issues or extra columns
    cols = "date, code, open, high, low, close, volume, amount, pctChg, turn"
    if not is_index:
        cols += ", tradestatus, isST, limit_up_price, limit_down_price, limit_status, preclose"
    else:
        cols += ", preclose"
        
    sql = f"SELECT {cols} FROM {table} WHERE code = '{code}'"
    if start_date:
        sql += f" AND date >= '{start_date}'"
    if end_date:
        sql += f" AND date <= '{end_date}'"
        
    sql += " ORDER BY date"
    
    df = ck_client.query_df(sql)
    if df.empty:
        return df
        
    # 3. Clean Types & Post-process
    df = df.reset_index(drop=True)
    
    # Ensure numeric
    num_cols = ['open', 'high', 'low', 'close', 'preclose', 'volume', 'amount']
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c])
            
    if 'date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['date']):
        df['date'] = pd.to_datetime(df['date'])

    # 4. Handle Suspensions (Fill Price with PreClose)
    # CK stores 0 for close on suspension days in some cases, but our ETL usually fills it?
    # Actually ETL fills limit price but open/close might be 0 if Baostock returns 0.
    # Safe bet: if tradestatus=0, set OHLC = preclose.
    if 'tradestatus' in df.columns:
        mask_suspend = df['tradestatus'] == 0
        if mask_suspend.any():
            # If suspended, OHLC = PreClose
            for col in ['open', 'high', 'low', 'close']:
                df.loc[mask_suspend, col] = df.loc[mask_suspend, 'preclose']
                
            # Volume/Amount should be 0, likely already 0
    
    # 5. Adjust (Factors)
    if adjust != 'none':
        # Query adjust_factor table
        # We fetch ALL factors for this code to ensure we have the right timeline
        sql_adj = f"SELECT dividOperateDate, foreAdjustFactor, backAdjustFactor FROM stock_data.adjust_factor WHERE code='{code}' ORDER BY dividOperateDate"
        factors = ck_client.query_df(sql_adj)
        
        if not factors.empty:
            factors['dividOperateDate'] = pd.to_datetime(factors['dividOperateDate'])
            factors = factors.sort_values('dividOperateDate')
            
            # Merge AsOf
            df = df.sort_values('date')
            df_merged = pd.merge_asof(
                df, 
                factors, 
                left_on='date', 
                right_on='dividOperateDate', 
                direction='backward'
            )
            
            # Fill missing factors. 
            # If date < first factor date, usage depends on logic.
            # Usually backFactor=1.0 initially.
            df_merged['backAdjustFactor'] = df_merged['backAdjustFactor'].fillna(method='ffill').fillna(1.0)
            df_merged['foreAdjustFactor'] = df_merged['foreAdjustFactor'].fillna(method='ffill').fillna(1.0)
            
            price_cols = ['open', 'high', 'low', 'close', 'preclose', 'limit_up_price', 'limit_down_price']
            # Filter cols that actually exist
            price_cols = [c for c in price_cols if c in df_merged.columns]

            if adjust == 'hfq':
                ratio = df_merged['backAdjustFactor']
                for col in price_cols:
                    df_merged[col] = df_merged[col] * ratio
            elif adjust == 'qfq':
                # QFQ = Price * (CurrentFactor / LatestFactor)
                # Latest factor should be the factor of the LATEST available date in the DB/market, 
                # NOT just the end_date of query. But for simplicity and consistency with standard qfq,
                # we usually take the last factor in the retrieving window OR the absolute latest.
                # Standard QFQ aligns to "Today".
                
                # Let's get the absolute latest factor from the factors DF we just queried
                latest_factor = factors['backAdjustFactor'].iloc[-1] if not factors.empty else 1.0
                
                # Careful: if the query window is in the past, 'latest_factor' from `factors` table (which has all history) 
                # is indeed the logic "align to today". 
                
                ratio = df_merged['backAdjustFactor'] / latest_factor
                for col in price_cols:
                    df_merged[col] = df_merged[col] * ratio
                    
            df = df_merged.drop(columns=['dividOperateDate', 'foreAdjustFactor', 'backAdjustFactor'])

    return df

