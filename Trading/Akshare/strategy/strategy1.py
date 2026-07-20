import os
import pandas as pd
from datetime import datetime
from market_data import fetch_and_clean_data
from stock_strategies import StrategyS1

def run_strategy_s1():
    # 1. 获取并清洗数据
    df_clean = fetch_and_clean_data()
    if df_clean.empty:
        print("停止执行: 未获取到有效数据。")
        return

    # 2. 执行策略
    print("正在执行策略 S1 (低市值低流通占比)...")
    strategy = StrategyS1()
    results = strategy.filter(df_clean)
    
    # 3. 保存结果
    today_str = datetime.now().strftime("%Y%m%d")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(project_root, "data", "strategy_result")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_file = os.path.join(output_dir, f"market_analysis_s1_{today_str}.xlsx")
    
    try:
        writer = pd.ExcelWriter(output_file, engine='xlsxwriter')
        
        # 保存全量数据 (可选，保持与旧脚本一致的行为，方便对比)
        df_clean.to_excel(writer, sheet_name='ALL', index=False)
        
        # 保存策略结果
        for sheet_name, df_res in results.items():
            df_res.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"[{sheet_name}] 筛选出 {len(df_res)} 只股票。")
            
        writer.close()
        print(f"分析文件已保存至: {output_file}")
    except Exception as e:
        print(f"保存文件失败: {e}")

if __name__ == "__main__":
    run_strategy_s1()
