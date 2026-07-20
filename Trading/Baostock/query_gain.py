from src.storage.ck_client import ck_client
import pandas as pd

# 1. 获取最近20个交易日
dates_df = ck_client.query_df("SELECT DISTINCT date FROM stock_data.stock_kline_day ORDER BY date DESC LIMIT 20")
if dates_df.empty:
    print("No data found")
    exit()

start_date = dates_df['date'].min()
end_date = dates_df['date'].max()

print(f"Analysis Period: {start_date} to {end_date}")

# 2. 查询涨幅超过30%的股票
# 使用 exp(sum(log(...))) 计算累积涨幅
sql = f"""
SELECT 
    s.code, 
    i.symbol, 
    round((exp(sum(log(1 + pctChg/100))) - 1) * 100, 2) as total_pct,
    count() as trade_days
FROM stock_data.stock_kline_day s
JOIN stock_data.securities_info i ON s.code = i.code
WHERE s.date >= '{start_date}' 
  AND s.pctChg > -99
  AND s.tradestatus = 1
GROUP BY s.code, i.symbol
HAVING total_pct > 30
ORDER BY total_pct DESC
"""

results = ck_client.query_df(sql)
if results.empty:
    print("No stocks found with >30% gain in the last 20 trading days.")
else:
    print(results.to_markdown(index=False))
