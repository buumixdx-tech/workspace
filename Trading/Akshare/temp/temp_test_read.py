import pandas as pd
import json
import sys

try:
    df = pd.read_excel(r'd:\WorkSpace\Trading\Akshare\data\stock_analysis\result_p5_20260309085921.xlsx')
    info = {
        "columns": df.columns.tolist(),
        "data": df.fillna("").head(3).to_dict("records")
    }
    print(json.dumps(info, ensure_ascii=False, indent=2))
except Exception as e:
    print("Error:", e, file=sys.stderr)
