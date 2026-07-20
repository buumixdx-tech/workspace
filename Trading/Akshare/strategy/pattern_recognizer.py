
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP

def calc_limit_price(prev_close, ratio):
    """
    Calculate limit up price: Round(Prev * (1+Ratio), 2)
    Standard rounding (ROUND_HALF_UP).
    """
    if pd.isna(prev_close) or prev_close == 0:
        return 0.0
    
    # Use Decimal for precise rounding
    # price = prev_close * (1 + ratio)
    # Convert inputs to string to assume exact conversion to decimal
    base = Decimal(str(prev_close))
    r = Decimal(str(ratio))
    target = base * (Decimal("1") + r)
    
    # Quantize to 0.00
    res = target.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    return float(res)

def identify_patterns(df_hist: pd.DataFrame, limit_ratio: float = 0.10):
    """
    Identify '2-into-3 failure' and '3-consecutive boards' patterns using strict price logic.
    
    Args:
        df_hist (pd.DataFrame): Daily K-line data, sorted by date ascending.
                                Columns expected: '日期', '收盘', '涨跌幅'
        limit_ratio (float): Limit Up Ratio. 0.10 for Main, 0.20 for KC/ChiNext.
        
    Returns:
        dict: {
            "fail_2_to_3_count": int,
            "fail_2_to_3_details": list[str],
            "board_3_count": int,
            "board_3_details": list[str]
        }
    """
    if df_hist.empty or len(df_hist) < 3:
        return {
            "fail_2_to_3_count": 0, "fail_2_to_3_details": [],
            "board_3_count": 0, "board_3_details": []
        }
    
    # Ensure sorted by date
    df = df_hist.sort_values("日期").reset_index(drop=True)
    
    # We need '收盘' column
    if "收盘" not in df.columns:
        return {
             "fail_2_to_3_count": 0, "fail_2_to_3_details": ["Error: Missing Close Price"],
             "board_3_count": 0, "board_3_details": []
        }

    # Calculate Limit Status for each day
    # We need previous close.
    # Shift '收盘' by 1 to get prev_close
    df["prev_close"] = df["收盘"].shift(1)
    
    # Vectorized calculation might be tricky with Decimal round, use loop or apply
    # For speed on 1 year data (250 rows), apply is fine.
    
    def check_limit(row):
        p_close = row["prev_close"]
        if pd.isna(p_close) or p_close == 0:
            return False
        
        limit_price = calc_limit_price(p_close, limit_ratio)
        # Compare Close with Limit Price
        # Strictly, Close should be equal (or >= due to float issues, but limit price is max)
        return row["收盘"] >= limit_price

    df["is_limit"] = df.apply(check_limit, axis=1)
    
    is_limit = df["is_limit"].tolist()
    
    fail_details = []
    board_details = []
    
    for i in range(2, len(df)):
        # Check for 2 limit ups before today
        prev_1_limit = is_limit[i-1]
        prev_2_limit = is_limit[i-2]
        
        if prev_2_limit and prev_1_limit:
            current_date = df.loc[i, "日期"]
            current_pct = df.loc[i, "涨跌幅"]
            
            if is_limit[i]:
                # Case: 3 Consecutive Boards
                next_pct_str = "N/A"
                if i + 1 < len(df):
                    next_pct = df.loc[i+1, "涨跌幅"]
                    next_pct_str = f"{next_pct:.2f}%"
                
                detail = f"{current_date} 后一日:{next_pct_str}"
                board_details.append(detail)
                
            else:
                # Case: 2-into-3 Failure
                detail = f"{current_date} 涨跌幅:{current_pct:.2f}%"
                fail_details.append(detail)
                
    return {
        "fail_2_to_3_count": len(fail_details),
        "fail_2_to_3_details": fail_details,
        "board_3_count": len(board_details),
        "board_3_details": board_details
    }
