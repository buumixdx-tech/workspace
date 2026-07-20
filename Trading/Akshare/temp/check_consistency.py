from market.ck_client import ClickHouseClient

def check():
    ck = ClickHouseClient()
    print("Securities Info (type=1) count:", ck.query_df("SELECT count() as c FROM securities_info WHERE type = 1")['c'].iloc[0])
    print("Stock K-line Day (2026-01-29) count:", ck.query_df("SELECT count() as c FROM stock_kline_day WHERE date = '2026-01-29'")['c'].iloc[0])
    
    print("\nSample Info Codes (type=1):")
    print(ck.query_df("SELECT code FROM securities_info WHERE type = 1 LIMIT 10")['code'].tolist())
    
    print("\nSample K-line Codes (2026-01-29):")
    print(ck.query_df("SELECT code FROM stock_kline_day WHERE date = '2026-01-29' LIMIT 10")['code'].tolist())
    
    # Check if any overlap exists
    overlap = ck.query_df("""
        SELECT count() as c
        FROM stock_kline_day k
        JOIN securities_info i ON k.code = i.code
        WHERE k.date = '2026-01-29' AND i.type = 1
    """)
    print("\nOverlap count (sh.xxxxxx == sh.xxxxxx):", overlap['c'].iloc[0])

if __name__ == "__main__":
    check()
