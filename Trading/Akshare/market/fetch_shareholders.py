import os
import time
import requests
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

import akshare as ak
import akshare as ak
import sys
import os

# Add parent directory to path to import from strategy
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategy.market_data import fetch_and_clean_data

# Define the user's required columns for CSV exactly
OUTPUT_COLUMNS = [
    "股票代码", "股票名称", "上市日期", "交易所", "板块", "是否ST", "总股本(万股)", "流通股本(万股)", 
    "总市值(亿)", "流通市值(亿)", "市值日期", "调整后流通市值(亿)", "调整因数", "股东数据更新日期"
]
# Append 30 columns for top 10 holders: Name, Ratio, Quantity
for i in range(1, 11):
    OUTPUT_COLUMNS.extend([f"十固股东{i}名称", f"十固股东{i}持股比例(%)", f"十固股东{i}持股数量"])
# Append 30 columns for top 10 tradable holdiers
for i in range(1, 11):
    OUTPUT_COLUMNS.extend([f"十流股东{i}名称", f"十流股东{i}持股比例(%)", f"十流股东{i}持股数量"])


def fetch_all_listing_dates():
    """Fetches listing dates for all A-share stocks and returns a dictionary mapping."""
    print("Fetching listing dates for all markets...")
    out = {}
    
    try:
        df_sz = ak.stock_info_sz_name_code()
        for _, row in df_sz.iterrows():
            out[str(row.get('A股代码'))] = str(row.get('A股上市日期'))
    except Exception:
        pass
        
    try:
        df_sh = ak.stock_info_sh_name_code()
        for _, row in df_sh.iterrows():
            out[str(row.get('代码', row.get('证券代码')))] = str(row.get('上市日期'))
    except Exception:
        pass
        
    try:
        df_bj = ak.stock_info_bj_name_code()
        for _, row in df_bj.iterrows():
            out[str(row.get('证券代码'))] = str(row.get('上市日期'))
    except Exception:
        pass
        
    return out


def fetch_base_stock_list():
    """Fetches the full market A-share spot data."""
    try:
        print("Fetching whole market spot data via Tencent Snapshot...")
        df_spot = fetch_and_clean_data()
        return df_spot
    except Exception as e:
        print(f"Error fetching base spot: {e}")
        return pd.DataFrame()


def process_single_stock(row, market_date_str, listing_dates_map):
    """Fetches shareholder data for a single stock and formats it according to output spec."""
    # Base info from spot
    code = str(row.get("股票代码", "")).strip()
    name = str(row.get("股票简称", "")).strip()
    if not code or not isinstance(code, str):
        return None
        
    is_st = "是" if "ST" in name.upper() else "否"
    
    pure_code_for_date = code.split(".")[-1] if "." in code else code
    listing_date = listing_dates_map.get(pure_code_for_date, "无数据")
    
    # 确定交易所和板块
    if code.startswith("SH."):
        exchange = "上交所"
        board = "科创板" if pure_code_for_date.startswith("68") else "主板"
    elif code.startswith("BJ."):
        exchange = "北交所"
        board = "主板"
    else:
        exchange = "深交所"
        board = "创业板" if pure_code_for_date.startswith("30") else "主板"
    
    # Calculate Cap in Billions (亿) and Shares in Ten-thousands (万)
    # 东方财富的 api 返回的是纯数字
    total_mcap = round(row.get("总市值", 0) / 100000000, 2) if pd.notna(row.get("总市值")) else 0
    float_mcap = round(row.get("流通市值", 0) / 100000000, 2) if pd.notna(row.get("流通市值")) else 0
    
    price = row.get("今天收盘价", 0)
    
    # Estimate total shares from mcap / price (since AKShare spot might not give explicit shares)
    total_shares = 0
    float_shares = 0
    if pd.notna(price) and price > 0:
        # 统一使用亿级别的数据重新转换为万股
        # (X 亿 * 100000000) / price / 10000 = X * 10000 / price
        total_shares = round((total_mcap * 10000) / price, 2)
        float_shares = round((float_mcap * 10000) / price, 2)
        
    result_dict = {
        "股票代码": code,
        "股票名称": name,
        "上市日期": listing_date,
        "交易所": exchange,
        "板块": board,
        "是否ST": is_st,
        "总股本(万股)": total_shares,
        "流通股本(万股)": float_shares,
        "总市值(亿)": total_mcap,
        "流通市值(亿)": float_mcap,
        "市值日期": market_date_str,
        "调整后流通市值(亿)": "",
        "调整因数": "",
        "股东数据更新日期": "无数据"
    }
    
    # Extract pure numeric code (remove SZ./SH./BJ. prefix)
    pure_code = code.split(".")[-1] if "." in code else code
    
    # Determine AKShare query format prefix
    if pure_code.startswith("6"):
        ak_code = f"sh{pure_code}"
    elif pure_code.startswith("8") or pure_code.startswith("4"):
        ak_code = f"bj{pure_code}"
    else:
        ak_code = f"sz{pure_code}"
        
    # Generate possible valid report dates backward (quarterly)
    today = datetime.today()
    report_dates = []
    for y in [today.year, today.year - 1]:
        report_dates.extend([f"{y}1231", f"{y}0930", f"{y}0630", f"{y}0331"])
    # Filter only dates that are physically in the past
    report_dates = [d for d in report_dates if d <= today.strftime("%Y%m%d")]
    report_dates.sort(reverse=True)
    
    # Try fetching the latest valid full quarterly report
    for d in report_dates:
        try:
            df_top10 = ak.stock_gdfx_top_10_em(symbol=ak_code, date=d)
            if df_top10 is not None and not df_top10.empty and len(df_top10) >= 10:
                
                # Fetch free (tradable) top 10 for the same date to validate
                try:
                    df_free10 = ak.stock_gdfx_free_top_10_em(symbol=ak_code, date=d)
                except Exception:
                    df_free10 = pd.DataFrame()
                    
                # Both lists MUST have 10 valid shareholders
                if df_free10 is None or df_free10.empty or len(df_free10) < 10:
                    continue
                    
                # Valid full baseline quarterly report found
                update_date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
                result_dict["股东数据更新日期"] = update_date
                
                # Fill Top 10 All (十大股东)
                for i in range(10):
                    prefix = f"十固股东{i+1}"
                    if i < len(df_top10):
                        row_data = df_top10.iloc[i]
                        result_dict[f"{prefix}名称"] = str(row_data.get("股东名称", ""))
                        result_dict[f"{prefix}持股比例(%)"] = str(row_data.get("占总股本持股比例", ""))
                        result_dict[f"{prefix}持股数量"] = str(row_data.get("持股数", ""))
                    else:
                        result_dict[f"{prefix}名称"] = ""
                        result_dict[f"{prefix}持股比例(%)"] = ""
                        result_dict[f"{prefix}持股数量"] = ""
                
                # Fill Top 10 Float (十大流通股东)
                for i in range(10):
                    prefix = f"十流股东{i+1}"
                    row_data = df_free10.iloc[i]
                    result_dict[f"{prefix}名称"] = str(row_data.get("股东名称", ""))
                    ratio = row_data.get("占总流通股本持股比例", row_data.get("占总股本持股比例", ""))
                    result_dict[f"{prefix}持股比例(%)"] = str(ratio)
                    result_dict[f"{prefix}持股数量"] = str(row_data.get("持股数", ""))
                
                # ============================================================
                # 计算调整因数
                # ============================================================
                adjust_factor = 1.0
                
                # 判断是否上市不超过一年
                listing_within_1_year = False
                try:
                    if listing_date and listing_date != "无数据":
                        from dateutil.relativedelta import relativedelta
                        listing_dt = datetime.strptime(listing_date, "%Y-%m-%d")
                        market_dt = datetime.strptime(market_date_str, "%Y-%m-%d")
                        if market_dt <= listing_dt + relativedelta(years=1):
                            listing_within_1_year = True
                except Exception:
                    pass
                
                if listing_within_1_year:
                    # 上市不超过一年，调整因数直接为1
                    adjust_factor = 1.0
                else:
                    # 找前十大股东中持股比例超过 5% 的股东名称
                    major_holders = set()
                    for i in range(len(df_top10)):
                        row_data = df_top10.iloc[i]
                        try:
                            ratio_val = float(row_data.get("占总股本持股比例", 0))
                        except (ValueError, TypeError):
                            ratio_val = 0
                        if ratio_val > 5:
                            holder_name = str(row_data.get("股东名称", "")).strip()
                            # 香港中央结算(HKSCC)代表的是港股通/外资流通持仓，不算锁定股东
                            if "香港中央结算" not in holder_name and "HKSCC" not in holder_name.upper():
                                major_holders.add(holder_name)
                    
                    # 在前十大流通股东中，找出这些大股东对应的流通股持股比例之和
                    sum_free_ratio = 0.0
                    for i in range(len(df_free10)):
                        row_data = df_free10.iloc[i]
                        holder_name = str(row_data.get("股东名称", "")).strip()
                        if holder_name in major_holders:
                            try:
                                free_ratio = float(row_data.get("占总流通股本持股比例", row_data.get("占总股本持股比例", 0)))
                            except (ValueError, TypeError):
                                free_ratio = 0
                            sum_free_ratio += free_ratio
                    
                    adjust_factor = round((100 - sum_free_ratio) / 100, 4)
                    # 确保范围在 [0, 1]
                    adjust_factor = max(0, min(1, adjust_factor))
                
                result_dict["调整因数"] = adjust_factor
                result_dict["调整后流通市值(亿)"] = round(float_mcap * adjust_factor, 2)
                
                # Successfully filled from a valid quarter, stop looking further back
                break
        except Exception:
            # If failed or no data for this specific quarter, try the previous one
            pass
            
    return result_dict


def main():
    start_time = time.time()
    
    # 1. Prepare Export Directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(project_root, "data", "strategy_result")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    market_date_str = datetime.now().strftime("%Y-%m-%d") # Or extract latest exact trade day
    output_filepath = os.path.join(output_dir, f"market_holders_{timestamp}.csv")
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始获取全市场行情...")
    df_spots = fetch_base_stock_list()
    
    if df_spots.empty:
        print("Error: Could not retrieve market data. Aborting.")
        return
        
    # Optional filtering here if needed (e.g. drop index or funds if any slip in, but A-share spot is usually clean)
    df_spots = df_spots[df_spots["股票代码"].astype(str).str.contains(r"\.?(00|30|60|68|43|83|87)")]
    total_stocks = len(df_spots)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 成功获取 {total_stocks} 只股票。准备并发抓取股东明细...")
    
    listing_dates_map = fetch_all_listing_dates()
    
    # 2. Concurrency Processing
    results = []
    # Setting workers directly to a reasonable number to prevent Eastmoney API ban
    max_workers = 16 
    
    # Convert dataframe to list of dicts for easily passing to thread pool
    tasks = df_spots.to_dict("records")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_stock = {executor.submit(process_single_stock, row, market_date_str, listing_dates_map): row["股票代码"] for row in tasks}
        
        for future in tqdm(as_completed(future_to_stock), total=total_stocks, desc="抓取股东数据"):
            code = future_to_stock[future]
            try:
                data = future.result()
                if data:
                    results.append(data)
            except Exception as exc:
                pass # Ignore single stock failure
                
    # 3. Create DataFrame and Order Columns Exactly as user specified
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 抓取完成，正在拼接并导出至 CSV...")
    df_result = pd.DataFrame(results)
    
    # Enforce Column Order and fill NaNs
    # Note: If any requested column wasn't generated somehow, ensure it exists with empty string
    for col in OUTPUT_COLUMNS:
        if col not in df_result.columns:
            df_result[col] = ""
            
    df_result = df_result[OUTPUT_COLUMNS]
    df_result.fillna("", inplace=True)
    
    # Export
    try:
        # Use utf-8-sig so it opens perfectly in Excel on Windows
        df_result.to_csv(output_filepath, index=False, encoding="utf-8-sig")
        print(f"\n[SUCCESS] 成功导出全市场 {len(df_result)} 家公司的详细股东台账。")
        print(f"文件位置: {output_filepath}")
        print(f"总耗时: {time.time() - start_time:.2f} 秒")
    except Exception as e:
        print(f"[ERROR] 保存 CSV 失败: {e}")

if __name__ == "__main__":
    main()
