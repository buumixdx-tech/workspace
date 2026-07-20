
import os
import sys
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.market_data import fetch_and_clean_data
from strategy.pattern_recognizer import identify_patterns

def get_historical_data(code, start_date, end_date):
    """
    Fetch historical daily data for a stock.
    """
    try:
        # akshare requires pure code like "600000" usually, or specific format
        # market_data.py formats as "SH.600000". We need to strip for some APIs, 
        # but stock_zh_a_hist takes pure code and 'adjust' param.
        clean_code = code.split(".")[-1]
        
        df_hist = ak.stock_zh_a_hist(
            symbol=clean_code, 
            period="daily", 
            start_date=start_date, 
            end_date=end_date, 
            adjust="" # Use Unadjusted for strict price check
        )
        return df_hist
    except Exception as e:
        print(f"Error fetching history for {code}: {e}")
        return pd.DataFrame()

def analyze_stock(row, start_date, end_date):
    """
    Analyze a single stock for Strategy 4 patterns.
    """
    code = row["股票代码"]
    name = row["股票简称"]
    total_mcap = row["总市值"]
    float_mcap = row["流通市值"]
    
    # Calculate Float Ratio
    float_ratio = 0.0
    if total_mcap > 0:
        float_ratio = float_mcap / total_mcap
    
    # Fetch History
    df_hist = get_historical_data(code, start_date, end_date)
    
    if df_hist.empty:
        return None
        
    # Determine Limit Up Ratio
    # 科创板(SH.688), 创业板(SZ.30xxx), 北交所(BJ) 涨跌幅限制为 20%
    if code.startswith("SH.688") or code.startswith("SZ.30") or code.startswith("BJ"):
        limit_ratio = 0.20
    else:
        limit_ratio = 0.10
        
    # Identification
    patterns = identify_patterns(df_hist, limit_ratio=limit_ratio)
    
    # If no patterns found, do we still keep it? 
    # User said: "统计池子中的每个票..." where pool is "appear 3-board OR 2-into-3 fail"? 
    # Actually description says: "在拉取的一年数据中出现过三连板的，构成池子。" (Step 2)
    # AND "统计池子中的每个票，二进三失败后...，三连扳后..."
    # So strictly, we only care if it has at least one "3-board" run?
    # Wait, Step 2 says: "appear 3-consecutive boards... constitute the pool".
    # But then Step 3 asks for "2-into-3 fail" stats for stocks IN THAT POOL.
    # So if a stock ONLY has "2-into-3 fail" but NEVER "3-board", it is NOT in the pool?
    # Let's verify strict reading:
    # "Step 2: In the fetched 1 year data, those that have appeared 3-consecutive boards constitute the pool."
    # So filtering condition is: board_3_count > 0.
    
    if patterns["board_3_count"] > 0:
        return {
            "股票代码": code,
            "股票名称": name,
            "总市值": total_mcap,
            "流通市值": float_mcap,
            "流通市值占比": float_ratio,
            "二进三失败次数": patterns["fail_2_to_3_count"],
            "二进三失败记录": "\n".join(patterns["fail_2_to_3_details"]),
            "三连板次数": patterns["board_3_count"],
            "三连板记录": "\n".join(patterns["board_3_details"])
        }
    return None

def run_strategy_s4(limit=None):
    print("=== 开始执行策略4: 三连板与二进三失败分析 ===")
    
    # 1. 获取并筛选基础数据
    df_base = fetch_and_clean_data()
    if df_base.empty:
        print("未获取到基础数据，退出。")
        return

    print(f"基础数据共 {len(df_base)} 条")
    
    # Filter: Non-ST, Non-BSE (Already handled mostly by stock code check but let's be safe), Float Ratio < 20%
    # Note: market_data.py handles ST/Delisting check if we look at it?
    # market_data.py adds "是否st".
    # BSE codes start with 8, 4, 92. market_data.py formats them as BJ.xxx.
    
    # 1.1 Exclude ST
    df_sel = df_base[df_base["是否st"] == "否"].copy()
    
    # 1.2 Exclude BSE (BJ)
    df_sel = df_sel[~df_sel["股票代码"].str.startswith("BJ")]
    
    # 1.3 Float Ratio < 20%
    # Ensure numeric
    df_sel["总市值"] = pd.to_numeric(df_sel["总市值"], errors='coerce')
    df_sel["流通市值"] = pd.to_numeric(df_sel["流通市值"], errors='coerce')
    
    # Avoid div by zero
    df_sel = df_sel[df_sel["总市值"] > 0]
    
    df_sel["float_ratio"] = df_sel["流通市值"] / df_sel["总市值"]
    df_sel["float_ratio"] = df_sel["流通市值"] / df_sel["总市值"]
    # 恢复流通占比过滤
    df_sel = df_sel[df_sel["float_ratio"] < 0.2]
    # print("Warning: 已暂时移除“流通占比 < 20%”的过滤条件，以扩大搜索范围。")
    
    print(f"初步筛选（非ST, 非北交所, 流通占比<20%）后剩余: {len(df_sel)} 只")
    
    if limit:
        print(f"测试模式：限制处理前 {limit} 只")
        df_sel = df_sel.head(limit)
        
    # 2. Historical Analysis (Concurrency)
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    
    results = []
    
    # Use ThreadPool
    max_workers = 10
    total_tasks = len(df_sel)
    print(f"开始获取历史数据并分析 (Time Range: {start_date} - {end_date})...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(analyze_stock, row, start_date, end_date): row["股票代码"] for _, row in df_sel.iterrows()}
        
        completed = 0
        for future in as_completed(futures):
            code = futures[future]
            completed += 1
            if completed % 50 == 0:
                print(f"进度: {completed}/{total_tasks}")
                
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as e:
                print(f"处理 {code} 出错: {e}")

    # 3. Save Results
    if not results:
        print("没有符合条件的股票（无三连板记录）。")
        return

    df_res = pd.DataFrame(results)
    
    # Sort by code
    df_res.sort_values("股票代码", inplace=True)
    
    today_str = datetime.now().strftime("%Y%m%d")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(project_root, "data", "strategy_result")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_file = os.path.join(output_dir, f"strategy4_result_{today_str}.xlsx")
    
    try:
        writer = pd.ExcelWriter(output_file, engine='xlsxwriter')
        df_res.to_excel(writer, index=False, sheet_name='Strategy4')
        
        workbook  = writer.book
        worksheet = writer.sheets['Strategy4']
        
        # Formats
        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center', 'valign': 'vcenter'
        })
        base_format = workbook.add_format({
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True
        })
        text_format = workbook.add_format({
            'border': 1, 'align': 'left', 'valign': 'top', 'text_wrap': True, 'font_size': 9
        })
        pct_format = workbook.add_format({
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '0.00%'
        })
        money_format = workbook.add_format({
             'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '#,##0.00'
        })
        
        # Columns
        cols = ["股票代码", "股票名称", "总市值", "流通市值", "流通市值占比", 
                "二进三失败次数", "二进三失败记录", "三连板次数", "三连板记录"]
        
        # Write Header
        for col_num, val in enumerate(cols):
            worksheet.write(0, col_num, val, header_format)
            
        # Write Data
        for row_idx, row_data in df_res.iterrows():
            row_num = row_idx + 1 # 0-indexed relative to df, but Excel row is +1 (header)
            # Actually iterrows index might not be sequential 0..N if filtered/sorted.
            # Better use enumerate on specific col list to be safe
            pass
            
        # Re-write data loop carefully
        for i in range(len(df_res)):
            item = df_res.iloc[i]
            worksheet.write(i+1, 0, item["股票代码"], base_format)
            worksheet.write(i+1, 1, item["股票名称"], base_format)
            worksheet.write(i+1, 2, item["总市值"], money_format)
            worksheet.write(i+1, 3, item["流通市值"], money_format)
            worksheet.write(i+1, 4, item["流通市值占比"], pct_format)
            worksheet.write(i+1, 5, item["二进三失败次数"], base_format)
            worksheet.write(i+1, 6, item["二进三失败记录"], text_format)
            worksheet.write(i+1, 7, item["三连板次数"], base_format)
            worksheet.write(i+1, 8, item["三连板记录"], text_format)

        # Widths
        worksheet.set_column('A:B', 12)
        worksheet.set_column('C:D', 15)
        worksheet.set_column('E:E', 10)
        worksheet.set_column('F:F', 10)
        worksheet.set_column('G:G', 40) # Details
        worksheet.set_column('H:H', 10)
        worksheet.set_column('I:I', 40) # Details
        
        writer.close()
        print(f"策略4分析完成，结果已保存至: {output_file}")
    except Exception as e:
        print(f"保存文件失败: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="Limit number of stocks")
    args = parser.parse_args()
    
    run_strategy_s4(limit=args.limit)
