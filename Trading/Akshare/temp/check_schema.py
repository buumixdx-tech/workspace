
import clickhouse_connect

def check_schema():
    try:
        client = clickhouse_connect.get_client(host='localhost', port=8123, username='admin', password='admin_password', database='stock_data')
        
        print("--- stock_kline_day Columns ---")
        result = client.query("DESCRIBE stock_kline_day")
        for row in result.result_rows:
            print(row[0], row[1])
            
        print("\n--- securities_info Columns ---")
        result = client.query("DESCRIBE securities_info")
        for row in result.result_rows:
            print(row[0], row[1])

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_schema()
