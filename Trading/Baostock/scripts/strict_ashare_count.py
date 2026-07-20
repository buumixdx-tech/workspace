
import baostock as bs
import pandas as pd
import re

def is_a_stock(code):
    """
    Strict A-share filter logic.
    SHA: 60xxxx, 688xxx (STAR)
    SZA: 00xxxx, 30xxxx (ChiNext)
    BJA: 4xxxxx, 8xxxxx
    """
    # Regex Patterns for A-share
    # SH Main: sh.60\d{4}
    # SH STAR: sh.688\d{3}
    # SH KC:   sh.689\d{3} (CDR)
    # SZ Main: sz.00\d{4}
    # SZ ChiNext: sz.30\d{4}
    # BJ: bj.4\d{5}, bj.8\d{5}
    
    # Exclude:
    # sh.900xxx (B share)
    # sz.200xxx (B share)
    # sh.5xxxxx (Fund/ETF)
    # sz.1xxxxx (Fund/Bond)
    # sh.000xxx (Index)
    # sz.399xxx (Index)
    
    if code.startswith('sh.60') or code.startswith('sh.68'): return True
    if code.startswith('sz.00') or code.startswith('sz.30'): return True
    if code.startswith('bj.4') or code.startswith('bj.8'): return True
    
    return False

def main():
    target_date = "2026-01-21"
    print(f"Fetching full snapshot for {target_date}...")
    bs.login()
    rs = bs.query_all_stock(day=target_date)
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    bs.logout()
    
    df = pd.DataFrame(data_list, columns=['code', 'tradeStatus', 'code_name'])
    print(f"Total Raw Securities: {len(df)}")
    
    # Apply Strict Filter
    df['is_A_share'] = df['code'].apply(is_a_stock)
    
    a_stocks = df[df['is_A_share']]
    others = df[~df['is_A_share']]
    
    print(f"\n[Strict A-Share Analysis]")
    print(f"Total A-Shares: {len(a_stocks)}")
    
    # Breakdown
    sh_main = len(a_stocks[a_stocks['code'].str.startswith('sh.60')])
    sh_star = len(a_stocks[a_stocks['code'].str.startswith('sh.68')])
    sz_main = len(a_stocks[a_stocks['code'].str.startswith('sz.00')])
    sz_cn   = len(a_stocks[a_stocks['code'].str.startswith('sz.30')])
    bj      = len(a_stocks[a_stocks['code'].str.contains('bj')])
    
    print(f"  - SH Main (60): {sh_main}")
    print(f"  - SH STAR (68): {sh_star}")
    print(f"  - SZ Main (00): {sz_main}")
    print(f"  - SZ ChiNext(30): {sz_cn}")
    print(f"  - BJ SE: {bj}")
    
    print(f"\n[Excluded Categories ({len(others)})]")
    # Sampling for verification
    print(f"Sample Excluded: {others['code'].head(10).tolist()}")

    # --- Save to Markdown Log ---
    import datetime
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_filename = f"ashare_list_{datetime.datetime.now().strftime('%Y%m%d')}.md"
    
    with open(log_filename, "w", encoding="utf-8") as f:
        f.write(f"# A-Share Stock List Log\n")
        f.write(f"**Generated Time**: {now_str}\n")
        f.write(f"**Total Count**: {len(a_stocks)}\n\n")
        f.write(f"| Code | Name | Status |\n")
        f.write(f"|---|---|---|\n")
        
        for _, row in a_stocks.iterrows():
            status_str = "Trading" if row['tradeStatus'] == '1' else "Halt"
            f.write(f"| {row['code']} | {row['code_name']} | {status_str} |\n")
            
    print(f"\nSuccessfully saved full list to {log_filename}")

if __name__ == "__main__":
    main()
