
import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from storage.ck_client import ck_client

tables = ck_client.query_df("SELECT name FROM system.tables WHERE database = 'stock_data'")['name'].tolist()
print("All tables in stock_data:")
for t in sorted(tables):
    print(f"- {t}")

print("\nMissing from Doc but in DB:")
known_in_doc = ['stock_kline_day', 'index_kline_day', 'stock_snapshot_intraday', 'trade_calendar', 'securities_info', 'adjust_factor', 'strategy_flu_params', 'view_strategy_flu', 'strategy_flu_stock_pool', 'view_strategy_flu_pool']
for t in sorted(tables):
    if t not in known_in_doc:
        print(f"- {t}")

print("\nIn Doc but missing from DB:")
for t in sorted(known_in_doc):
    if t not in tables:
        print(f"- {t}")
