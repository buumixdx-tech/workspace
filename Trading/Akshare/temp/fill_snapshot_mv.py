
import clickhouse_connect
import pandas as pd
from datetime import datetime, time

def fill_snapshot_mv():
    try:
        # Connect to ClickHouse
        client = clickhouse_connect.get_client(
            host='localhost', 
            port=8123, 
            username='admin', 
            password='admin_password', 
            database='stock_data'
        )
        print("Connected to ClickHouse.")

        # 1. Get the latest date from stock_kline_day
        latest_date_query = "SELECT max(date) as max_date FROM stock_kline_day"
        latest_date_df = client.query_df(latest_date_query)
        
        if latest_date_df.empty or latest_date_df['max_date'].iloc[0] is None:
            print("Error: No data in stock_kline_day.")
            return

        latest_date = latest_date_df['max_date'].iloc[0]
        # Ensure latest_date is a date object
        if hasattr(latest_date, 'date'):
             latest_date_obj = latest_date.date()
        else:
             # pandas timestamp or other
             latest_date_obj = latest_date
        
        date_str = latest_date_obj.strftime('%Y-%m-%d')
        print(f"Latest K-line Date: {date_str}")

        # 2. Fetch K-line data for this date
        # Getting necessary columns to reconstruct snapshot + calc MV
        kline_sql = f"""
        SELECT 
            code,
            close,
            open,
            high,
            low,
            preclose,
            volume,
            amount,
            turn,
            pctChg,
            tradestatus
        FROM stock_kline_day
        WHERE date = '{date_str}'
        """
        kline_df = client.query_df(kline_sql)
        print(f"Fetched {len(kline_df)} K-line records.")

        # 3. Fetch Securities Info (for Total Shares and Name)
        # Note: securities_info might describe multiple entries? No, code is LowCardinality(String).
        # Assuming unique code in securities_info or taking valid ones.
        sec_sql = "SELECT code, symbol as name, total_shares FROM securities_info"
        sec_df = client.query_df(sec_sql)
        print(f"Fetched {len(sec_df)} Security records.")

        # 4. Merge Data
        # Left join on code
        merged_df = pd.merge(kline_df, sec_df, on='code', how='inner') # Use inner to ensure we have shares info
        
        if merged_df.empty:
            print("Error: No matching records between K-line and Securities Info.")
            return

        # 5. Calculate Market Caps and Fields
        # Total Market Cap = Close * Total Shares
        merged_df['total_market_cap'] = merged_df['close'] * merged_df['total_shares']
        
        # Float Market Cap
        # Float Shares = Volume / (Turnover% / 100) -> Volume * 100 / Turn
        # Handle turn = 0
        def calc_float_mv(row):
            if row['turn'] > 0:
                float_shares = (row['volume'] * 100) / row['turn']
                return float_shares * row['close']
            else:
                return 0.0

        merged_df['float_market_cap'] = merged_df.apply(calc_float_mv, axis=1)

        # 6. Prepare DataFrame for stock_snapshot_intraday
        # Target Columns: 
        # ['code', 'name', 'snapshot_time', 'source_time', 'price', 
        #  'open', 'high', 'low', 'last_close', 'change', 'pct_chg', 
        #  'volume', 'amount', 'turnover_rate', 'total_market_cap', 
        #  'float_market_cap', 'is_suspended']
        
        # Construct Snapshot Time (EOD: 15:00:00)
        snapshot_time = datetime.combine(latest_date_obj, time(15, 0, 0))
        
        output_df = pd.DataFrame()
        output_df['code'] = merged_df['code']
        output_df['name'] = merged_df['name']
        output_df['snapshot_time'] = snapshot_time
        output_df['source_time'] = snapshot_time # Use same time or slightly varied? usually same.
        
        output_df['price'] = merged_df['close']
        output_df['open'] = merged_df['open']
        output_df['high'] = merged_df['high']
        output_df['low'] = merged_df['low']
        output_df['last_close'] = merged_df['preclose']
        
        output_df['change'] = merged_df['close'] - merged_df['preclose']
        output_df['pct_chg'] = merged_df['pctChg']
        
        output_df['volume'] = merged_df['volume']
        output_df['amount'] = merged_df['amount']
        output_df['turnover_rate'] = merged_df['turn']
        
        output_df['total_market_cap'] = merged_df['total_market_cap']
        output_df['float_market_cap'] = merged_df['float_market_cap']
        
        # is_suspended: tradestatus 1=Normal, 0=Suspended. 
        # snapshot: is_suspended 1=Yes, 0=No.
        output_df['is_suspended'] = (1 - merged_df['tradestatus']).astype('uint8') 

        # 7. Insert into ClickHouse
        # Using insert_df which handles large inserts
        print("Inserting records into stock_snapshot_intraday...")
        client.insert_df('stock_snapshot_intraday', output_df)
        print(f"Successfully inserted/updated {len(output_df)} records.")

        # 8. Verify
        verify_sql = f"SELECT count() FROM stock_snapshot_intraday WHERE snapshot_time = '{snapshot_time}'"
        count = client.query(verify_sql).result_rows[0][0]
        print(f"Verification: {count} records found for snapshot_time {snapshot_time}.")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fill_snapshot_mv()
