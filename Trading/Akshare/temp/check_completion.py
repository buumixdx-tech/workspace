import os
import pandas as pd
import glob

def main():
    stockpool_path = r"d:\WorkSpace\Trading\Akshare\data\stock_analysis\stockpool_p5_20260306.xlsx"
    p5_dir = r"d:\WorkSpace\Trading\Akshare\data\stock_analysis\p5"
    
    if not os.path.exists(stockpool_path):
        print(f"Error: {stockpool_path} not found.")
        return
    
    # 1. 获取已处理的股票代码列表
    md_files = glob.glob(os.path.join(p5_dir, "*.md"))
    processed_codes = {os.path.splitext(os.path.basename(f))[0] for f in md_files}
    
    print(f"Total processed files found: {len(processed_codes)}")
    
    # 2. 读取 Excel
    try:
        df = pd.read_excel(stockpool_path)
    except Exception as e:
        print(f"Error reading excel: {e}")
        return
    
    if df.empty:
        print("Excel is empty.")
        return
        
    code_col = df.columns[0]
    
    # 3. 标识是否处理完
    def check_processed(code):
        # 统一格式化：移除点号
        cleaned = str(code).replace('.', '')
        return "是" if cleaned in processed_codes else "否"
    
    df['是否处理完'] = df[code_col].apply(check_processed)
    
    # 4. 保存文件
    # 另存为一个新文件，或者覆盖原文件。用户要求在原文件中标识，所以我们覆盖。
    try:
        df.to_excel(stockpool_path, index=False)
        print(f"Success: Updated {stockpool_path}")
        
        # 统计
        processed_count = (df['是否处理完'] == "是").sum()
        total_count = len(df)
        print(f"Summary: {processed_count}/{total_count} stocks processed.")
        
    except Exception as e:
        print(f"Error saving excel: {e}")

if __name__ == "__main__":
    main()
