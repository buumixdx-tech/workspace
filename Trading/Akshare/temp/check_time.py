
import clickhouse_connect
from datetime import datetime

try:
    client = clickhouse_connect.get_client(
        host='localhost', 
        port=8123, 
        username='admin', 
        password='admin_password', 
        database='stock_data'
    )
    
    # Check the latest snapshot time for market cap
    result = client.query("SELECT max(snapshot_time) FROM stock_snapshot_intraday").first_row
    snapshot_time = result[0]
    
    print(f"Latest Snapshot Time: {snapshot_time}")
    
    # Also check if it matches the current date logic
    if snapshot_time:
        print(f"Date: {snapshot_time.date()}")
    else:
        print("Table is empty")
        
except Exception as e:
    print(f"Connection Error: {e}")
