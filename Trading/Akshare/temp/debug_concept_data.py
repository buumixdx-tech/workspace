
import pandas as pd
from market.ck_client import ClickHouseClient

def debug_data():
    ck = ClickHouseClient()
    try:
        # 1. 查列名
        print("--- Table Schema: concept_snapshot_intraday ---")
        cols = ck.query_df("DESCRIBE concept_snapshot_intraday")
        print(cols['name'].tolist())

        # 2. Check latest snapshot time
        time_df = ck.query_df("SELECT max(snapshot_time) as t FROM stock_snapshot_intraday")
        latest_time = time_df['t'].iloc[0]
        print(f"\nLatest Snapshot Time: {latest_time}")
        
        # 3. Check specific stock that SHOULD be limit up
        print("\n--- Stock Limit Up Analysis (Sample: sh.688380 or Top 1) ---")
        stock_sql = f"""
            SELECT code, name, price, last_close, pct_chg, 
            multiIf(code LIKE 'bj.%', 0.30, (code LIKE 'sz.30%') OR (code LIKE 'sh.688%'), 0.20, name LIKE '%ST%', 0.05, 0.10) as ratio,
            round(last_close * (1 + multiIf(code LIKE 'bj.%', 0.30, (code LIKE 'sz.30%') OR (code LIKE 'sh.688%'), 0.20, name LIKE '%ST%', 0.05, 0.10)), 2) as limit_price_calc,
            if(price >= limit_price_calc, 'YES', 'NO') as is_limit_up
            FROM stock_snapshot_intraday
            WHERE snapshot_time = '{latest_time}'
            ORDER BY pct_chg DESC 
            LIMIT 5
        """
        print(ck.query_df(stock_sql))
        
        # 4. Check for Duplicates (Crucial for Append-Only tables)
        print(f"\n--- Checking Duplicates for time: {latest_time} ---")
        dup_sql = f"""
            SELECT concept_name, count() as cnt 
            FROM concept_snapshot_intraday 
            WHERE snapshot_time = '{latest_time}'
            GROUP BY concept_name
            HAVING cnt > 1
            LIMIT 5
        """
        print(ck.query_df(dup_sql))
        
        # 5. Check Data Quality (NaN or Zero LimitUps)
        print("\n--- Data Quality Check (Concepts with >0 LimitUps) ---")
        quality_sql = f"""
            SELECT concept_name, pct_chg, limit_up_count, stock_count
            FROM concept_snapshot_intraday
            WHERE snapshot_time = '{latest_time}'
            ORDER BY limit_up_count DESC
            LIMIT 5
        """
        print(ck.query_df(quality_sql))

        print("\n--- Data Quality Check (NaN pct_chg check) ---")
        nan_sql = f"""
            SELECT concept_name, pct_chg, limit_up_count
            FROM concept_snapshot_intraday
            WHERE snapshot_time = '{latest_time}' AND isNaN(pct_chg)
            LIMIT 5
        """
        print(ck.query_df(nan_sql))

    except Exception as e:
        print(f"Error: {e}")
    finally:
        ck.close()

if __name__ == "__main__":
    debug_data()
