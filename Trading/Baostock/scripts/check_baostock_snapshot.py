
import baostock as bs
import pandas as pd
import datetime

def main():
    target_date = "2026-01-21"
    print(f"Checking Baostock active securities for {target_date}...")
    
    bs.login()
    
    # query_all_stock returns all stocks listed on that day
    # This includes suspended stocks (tradestatus=0) but excludes delisted ones (before that date)
    rs = bs.query_all_stock(day=target_date)
    
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    
    bs.logout()
    
    if not data_list:
        print(f"No securities found for {target_date}. Is it a weekend/holiday?")
        # If it's a holiday, query_all_stock might return nothing?
        # Baostock usually returns the list of *listed* securities regardless of holiday, 
        # but let's see. If 2026-01-21 is Sunday, maybe empty?
        # Actually Baostock documentation says "day: query date".
        return

    df = pd.DataFrame(data_list, columns=['code', 'tradeStatus', 'code_name'])
    
    # Categorize
    # Baostock doesn't explicitly give type in query_all_stock.
    # We infer by code prefix.
    
    def get_type(code):
        if code.startswith('sh.000') or code.startswith('sz.399'):
            return 'Index'
        return 'Stock'
    
    df['type'] = df['code'].apply(get_type)
    
    # Further breakdown: Suspended vs Trading
    # tradeStatus: 1=Normal, 0=Halt
    
    print(f"\n--- Baostock Snapshot {target_date} ---")
    print(f"Total Securities: {len(df)}")
    
    print("\n[Stocks]")
    stocks = df[df['type'] == 'Stock']
    n_stocks = len(stocks)
    n_stock_trade = len(stocks[stocks['tradeStatus'] == '1'])
    n_stock_halt = len(stocks[stocks['tradeStatus'] == '0'])
    print(f"Total: {n_stocks}")
    print(f"  - Trading: {n_stock_trade}")
    print(f"  - Halted:  {n_stock_halt}")
    
    print("\n[Indices]")
    indices = df[df['type'] == 'Index']
    n_idx = len(indices)
    print(f"Total: {n_idx}")
    
    print("\nSample Stocks:")
    print(stocks.head(3)['code'].tolist())
    print("Sample Indices:")
    print(indices.head(3)['code'].tolist())

if __name__ == "__main__":
    main()
