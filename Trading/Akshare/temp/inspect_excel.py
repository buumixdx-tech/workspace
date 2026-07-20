import pandas as pd
import os

file_path = r'd:\WorkSpace\Trading\Akshare\data\strategy_result\market_analysis_s4.xlsx'
if os.path.exists(file_path):
    try:
        xls = pd.ExcelFile(file_path)
        print(f"Sheets: {xls.sheet_names}")
        for sheet in xls.sheet_names[:3]: # look at first few sheets
            df = pd.read_excel(file_path, sheet_name=sheet, nrows=5)
            print(f"\nSheet: {sheet}")
            print(f"Columns: {df.columns.tolist()}")
            print("First 2 rows:")
            print(df.head(2).to_string())
    except Exception as e:
        print(f"Error: {e}")
else:
    print("File not found.")
