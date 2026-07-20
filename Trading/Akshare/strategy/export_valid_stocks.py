
import os
import sys
import pandas as pd
import akshare as ak

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategy.market_data import fetch_and_clean_data

def export_valid_stocks():
    print("=== 开始筛选符合约束条件的股票 ===")
    
    # 1. 获取并筛选基础数据
    # fetch_and_clean_data 已包含逻辑：
    # - 获取 stock_zh_a_spot_em
    # - 格式化代码
    # - 剔除退市 (交易异常且无价格)
    # - 标记ST
    df_base = fetch_and_clean_data()
    
    if df_base.empty:
        print("未获取到基础数据，退出。")
        return

    print(f"基础数据共 {len(df_base)} 条")
    
    # 2. 执行与 Strategy 4 相同的筛选逻辑
    
    # 2.1 剔除 ST
    df_sel = df_base[df_base["是否st"] == "否"].copy()
    
    # 2.2 剔除 北交所 (BJ)
    df_sel = df_sel[~df_sel["股票代码"].str.startswith("BJ")]
    
    # 2.3 流通市值占比 < 20%
    # 确保数值类型
    df_sel["总市值"] = pd.to_numeric(df_sel["总市值"], errors='coerce')
    df_sel["流通市值"] = pd.to_numeric(df_sel["流通市值"], errors='coerce')
    
    # 避免除以零
    df_sel = df_sel[df_sel["总市值"] > 0]
    
    # 计算占比
    df_sel["float_ratio"] = df_sel["流通市值"] / df_sel["总市值"]
    
    # 筛选 < 20%
    df_filtered = df_sel[df_sel["float_ratio"] < 0.2]
    
    print(f"筛选结果：符合条件的股票共 {len(df_filtered)} 只")
    
    # 3. 格式化输出列
    # 需要: 代码、名称、最新的市值、流通市值
    # 额外加上 float_ratio 方便查看
    output_df = df_filtered[["股票代码", "股票简称", "总市值", "流通市值", "float_ratio"]].copy()
    output_df.columns = ["Code", "Name", "Total_Market_Cap", "Float_Market_Cap", "Float_Ratio"]
    
    # sort by code
    output_df.sort_values("Code", inplace=True)
    
    # 4. 保存到 CSV
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(project_root, "data", "temp_export")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_file = os.path.join(output_dir, "valid_stocks_export.csv")
    
    # 保存 utf-8-sig 方便 Excel 打开不乱码
    output_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    
    print(f"结果已保存至: {output_file}")
    
    # Preview
    print("\n前5条预览:")
    print(output_df.head().to_string())

if __name__ == "__main__":
    export_valid_stocks()
