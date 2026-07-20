import pandas as pd
import os
from stock_analysis.types import StockTask

def create_task_from_row(row) -> StockTask:
    name_val = row.get("股票名称", row.get("股票简称", row.get("名称", row.get("name", ""))))
    code_val = row.get("股票代码", row.get("code", ""))
    return StockTask(
        code=str(code_val).strip(),
        name=str(name_val).strip() if pd.notna(name_val) and str(name_val).strip() != "nan" else "",
        total_mcap=row.get("总市值", 0),
        float_mcap=row.get("流通市值", 0),
    )

file_path = r'd:\WorkSpace\Trading\Akshare\data\strategy_result\market_analysis_s4.xlsx'
df = pd.read_excel(file_path, sheet_name='Selected')

cols_to_fill = [c for c in ["股票代码", "股票名称", "股票简称", "名称"] if c in df.columns]
if cols_to_fill:
    print(f"Filling columns: {cols_to_fill}")
    df[cols_to_fill] = df[cols_to_fill].ffill()

tasks = [create_task_from_row(row) for _, row in df.head(5).iterrows()]
for t in tasks:
    print(f"Code: {t.code}, Name: '{t.name}'")
